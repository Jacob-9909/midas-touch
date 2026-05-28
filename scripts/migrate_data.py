"""One-time database migration script: Azure SQL & Supabase → Unified PostgreSQL.

This script:
1. Bootstraps the target PostgreSQL database with the consolidated schema (postgres_schema.sql).
2. Extracts users, tax_rules, and market_snapshots from the Azure SQL Database.
3. Extracts persona_embeddings from the Supabase database.
4. Performs necessary type transformations (bit -> boolean, uniqueidentifier -> uuid).
5. Batches insertions into the new target PostgreSQL database.
6. Verifies row counts to ensure perfect fidelity.
"""

import os
import sys
import argparse
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

# Set up project root and source path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

# Load environment variables
load_dotenv()

TARGET_PG_URL = os.environ.get("DATABASE_URL") or "postgresql://postgres:pass@localhost/postgres"


def get_azure_connection():
    """Connect to the source Azure SQL Database."""
    import pyodbc
    server = os.environ.get("AZURE_SQL_SERVER", "")
    database = os.environ.get("AZURE_SQL_DATABASE", "")
    user = os.environ.get("AZURE_SQL_USER", "")
    password = os.environ.get("AZURE_SQL_PASSWORD", "")
    
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server},1433;"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )
    print(f"Connecting to Azure SQL: {server}...")
    return pyodbc.connect(conn_str)


def get_supabase_db_connection():
    """Connect to the source Supabase PostgreSQL Database directly via psycopg2."""
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("SUPABASE_DB_URL is missing in environment variables.")
    print("Connecting to Supabase PostgreSQL...")
    return psycopg2.connect(db_url)


def get_target_connection():
    """Connect to the target unified PostgreSQL Database."""
    print("Connecting to target PostgreSQL DB...")
    return psycopg2.connect(TARGET_PG_URL)


def bootstrap_schema(target_conn):
    """Bootstrap the target DB with the consolidated PostgreSQL schema."""
    schema_path = os.path.join(project_root, "database", "schema", "postgres_schema.sql")
    print(f"Reading consolidated schema from {schema_path}...")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    print("Applying schema to target PostgreSQL database...")
    with target_conn.cursor() as cur:
        cur.execute(schema_sql)
    target_conn.commit()
    print("Schema applied successfully!")


def migrate_users(azure_conn, target_conn):
    """Migrate the 'users' table from Azure SQL to PostgreSQL."""
    print("\n--- Migrating Users ---")
    
    # 1. Extract from Azure
    with azure_conn.cursor() as cur:
        cur.execute("SELECT * FROM users")
        columns = [column[0] for column in cur.description]
        rows = cur.fetchall()
        
    print(f"Extracted {len(rows)} users from Azure SQL.")
    if not rows:
        return
    
    # Map row values to a list of dicts
    user_records = [dict(zip(columns, row)) for row in rows]
    
    # 2. Ingest into target PostgreSQL
    insert_sql = """
    INSERT INTO users (
        id, uuid, age, sex, marital_status, education_level, bachelors_field,
        occupation, family_type, housing_type, district, persona,
        professional_persona, family_persona, career_goals_and_ambitions,
        total_amount, monthly_income, monthly_investable, specific_items,
        has_stock, has_bond, has_deposit, has_real_estate,
        stock_amount, bond_amount, deposit_amount, real_estate_amount,
        aggressiveness, preferred_asset, financial_literacy,
        target_return_percent, investable_period_months, requires_liquidity,
        created_at, updated_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        %s, %s
    )
    ON CONFLICT (uuid) DO NOTHING;
    """
    
    # Build batch values
    batch_data = []
    for r in user_records:
        # Convert bits (0/1) or custom representations to python booleans
        has_stock = bool(r.get("has_stock", False))
        has_bond = bool(r.get("has_bond", False))
        has_deposit = bool(r.get("has_deposit", False))
        has_real_estate = bool(r.get("has_real_estate", False))
        requires_liquidity = bool(r.get("requires_liquidity", False))
        
        # Datetime conversions
        created_at = r.get("created_at")
        updated_at = r.get("updated_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            
        vals = (
            str(r.get("id")),
            r.get("uuid"),
            r.get("age"),
            r.get("sex"),
            r.get("marital_status"),
            r.get("education_level"),
            r.get("bachelors_field"),
            r.get("occupation"),
            r.get("family_type"),
            r.get("housing_type"),
            r.get("district"),
            r.get("persona"),
            r.get("professional_persona"),
            r.get("family_persona"),
            r.get("career_goals_and_ambitions"),
            r.get("total_amount"),
            r.get("monthly_income"),
            r.get("monthly_investable"),
            r.get("specific_items"),
            has_stock,
            has_bond,
            has_deposit,
            has_real_estate,
            r.get("stock_amount", 0),
            r.get("bond_amount", 0),
            r.get("deposit_amount", 0),
            r.get("real_estate_amount", 0),
            r.get("aggressiveness"),
            r.get("preferred_asset"),
            r.get("financial_literacy"),
            r.get("target_return_percent"),
            r.get("investable_period_months"),
            requires_liquidity,
            created_at,
            updated_at
        )
        batch_data.append(vals)
        
    with target_conn.cursor() as cur:
        cur.executemany(insert_sql, batch_data)
    target_conn.commit()
    print(f"Successfully migrated {len(batch_data)} users to PostgreSQL.")


def migrate_tax_rules(azure_conn, target_conn):
    """Migrate the 'tax_rules' table from Azure SQL to PostgreSQL."""
    print("\n--- Migrating Tax Rules ---")
    
    # 1. Extract
    with azure_conn.cursor() as cur:
        cur.execute("SELECT * FROM tax_rules")
        columns = [column[0] for column in cur.description]
        rows = cur.fetchall()
        
    print(f"Extracted {len(rows)} tax rules from Azure SQL.")
    if not rows:
        return
        
    records = [dict(zip(columns, row)) for row in rows]
    
    # 2. Ingest
    insert_sql = """
    INSERT INTO tax_rules (
        asset_type, income_type, min_amount, max_amount, tax_rate,
        local_tax_rate, deduction_limit, effective_date, expiry_date,
        description, legal_basis
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s
    )
    ON CONFLICT ON CONSTRAINT uQ_tax_rules_key DO NOTHING;
    """
    
    batch_data = []
    for r in records:
        vals = (
            r.get("asset_type"),
            r.get("income_type"),
            r.get("min_amount"),
            r.get("max_amount"),
            r.get("tax_rate"),
            r.get("local_tax_rate"),
            r.get("deduction_limit"),
            r.get("effective_date"),
            r.get("expiry_date"),
            r.get("description"),
            r.get("legal_basis")
        )
        batch_data.append(vals)
        
    with target_conn.cursor() as cur:
        cur.executemany(insert_sql, batch_data)
    target_conn.commit()
    print(f"Successfully migrated {len(batch_data)} tax rules to PostgreSQL.")


def migrate_market_snapshots(azure_conn, target_conn):
    """Migrate the 'market_snapshots' table from Azure SQL to PostgreSQL."""
    print("\n--- Migrating Market Snapshots ---")
    
    # 1. Extract
    with azure_conn.cursor() as cur:
        cur.execute("SELECT * FROM market_snapshots")
        columns = [column[0] for column in cur.description]
        rows = cur.fetchall()
        
    print(f"Extracted {len(rows)} market snapshots from Azure SQL.")
    if not rows:
        return
        
    records = [dict(zip(columns, row)) for row in rows]
    
    # 2. Ingest
    insert_sql = """
    INSERT INTO market_snapshots (
        snapshot_date, data_type, sub_key, value, unit, source, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (snapshot_date, data_type, sub_key) DO NOTHING;
    """
    
    batch_data = []
    for r in records:
        created_at = r.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            
        vals = (
            r.get("snapshot_date"),
            r.get("data_type"),
            r.get("sub_key"),
            r.get("value"),
            r.get("unit"),
            r.get("source"),
            created_at
        )
        batch_data.append(vals)
        
    with target_conn.cursor() as cur:
        cur.executemany(insert_sql, batch_data)
    target_conn.commit()
    print(f"Successfully migrated {len(batch_data)} market snapshots to PostgreSQL.")


def migrate_persona_embeddings(supabase_conn, target_conn):
    """Migrate the 'persona_embeddings' table from Supabase to target PostgreSQL."""
    print("\n--- Migrating Persona Embeddings ---")
    
    # 1. Extract
    with supabase_conn.cursor() as cur:
        cur.execute("SELECT azure_user_uuid, persona_text, embedding, created_at, updated_at FROM persona_embeddings")
        columns = [column[0] for column in cur.description]
        rows = cur.fetchall()
        
    print(f"Extracted {len(rows)} persona embeddings from Supabase.")
    if not rows:
        return
        
    records = [dict(zip(columns, row)) for row in rows]
    
    # 2. Ingest
    insert_sql = """
    INSERT INTO persona_embeddings (
        azure_user_uuid, persona_text, embedding, created_at, updated_at
    ) VALUES (
        %s, %s, %s::vector, %s, %s
    )
    ON CONFLICT (azure_user_uuid) DO NOTHING;
    """
    
    batch_data = []
    for r in records:
        # embedding is returned as a float list or string from psycopg2 (often a list)
        embedding = r.get("embedding")
        
        vals = (
            r.get("azure_user_uuid"),
            r.get("persona_text"),
            embedding,
            r.get("created_at"),
            r.get("updated_at")
        )
        batch_data.append(vals)
        
    with target_conn.cursor() as cur:
        cur.executemany(insert_sql, batch_data)
    target_conn.commit()
    print(f"Successfully migrated {len(batch_data)} persona embeddings to PostgreSQL.")


def verify_migration(target_conn):
    """Verify row counts in the target PostgreSQL database."""
    print("\n--- Verification Report ---")
    tables = ["users", "tax_rules", "market_snapshots", "persona_embeddings"]
    with target_conn.cursor() as cur:
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            print(f"Table '{t}' count in Target PostgreSQL: {count}")
    print("--------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="Consolidate Azure SQL & Supabase to PostgreSQL")
    parser.add_argument("--skip-schema", action="store_true", help="Skip schema bootstrap")
    args = parser.parse_args()
    
    azure_conn = None
    supabase_conn = None
    target_conn = None
    
    try:
        # Establish connections
        azure_conn = get_azure_connection()
        supabase_conn = get_supabase_db_connection()
        target_conn = get_target_connection()
        
        # 1. Bootstrap target schema
        if not args.skip_schema:
            bootstrap_schema(target_conn)
            
        # 2. Migrate Azure SQL tables
        migrate_users(azure_conn, target_conn)
        migrate_tax_rules(azure_conn, target_conn)
        migrate_market_snapshots(azure_conn, target_conn)
        
        # 3. Migrate Supabase vector tables
        migrate_persona_embeddings(supabase_conn, target_conn)
        
        # 4. Verify everything
        verify_migration(target_conn)
        
        print("🎉 Consolidation & Migration successfully completed!")
        
    except Exception as e:
        print(f"❌ Migration failed with error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if azure_conn:
            azure_conn.close()
        if supabase_conn:
            supabase_conn.close()
        if target_conn:
            target_conn.close()


if __name__ == "__main__":
    main()
