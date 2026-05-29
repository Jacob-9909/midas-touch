"""Unit test suite for Midas Touch RAG advisor agent & database helper functions.

Run tests:
    python -m unittest tests/test_agent.py
"""

import os
import sys
import unittest

# Set up project root and source path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from dotenv import load_dotenv
load_dotenv()

from agent.recommender import MidasAdviser
from db.connector import (
    get_all_tax_rules,
    get_latest_market_snapshots,
    get_user_by_uuid,
    search_similar_personas_db,
)


class TestMidasAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Check environment variables
        cls.has_env = os.path.exists(os.path.join(project_root, ".env"))
        if not cls.has_env:
            print("⚠️ Warning: .env file missing. Some integration tests might fail.")

    def test_get_all_tax_rules(self) -> None:
        """Test retrieving tax rules from Azure SQL Database."""
        try:
            tax_rules = get_all_tax_rules()
            self.assertIsInstance(tax_rules, list, "Tax rules should be returned as a list.")
            if len(tax_rules) > 0:
                rule = tax_rules[0]
                self.assertIn("asset_type", rule, "Tax rule dict should contain key 'asset_type'.")
                self.assertIn("tax_rate", rule, "Tax rule dict should contain key 'tax_rate'.")
                print(f"✅ Azure SQL Tax Rules integration succeeded! Retrieved {len(tax_rules)} rules.")
            else:
                print("ℹ️ Azure SQL Tax Rules table is empty, but query executed successfully.")
        except Exception as e:
            self.fail(f"Failed to query tax_rules from Azure SQL: {e}")

    def test_get_latest_market_snapshots(self) -> None:
        """Test retrieving latest market snapshots from Azure SQL."""
        try:
            snapshots = get_latest_market_snapshots()
            self.assertIsInstance(snapshots, list, "Market snapshots should be returned as a list.")
            if len(snapshots) > 0:
                snap = snapshots[0]
                self.assertIn("snapshot_date", snap, "Snapshot dict should contain key 'snapshot_date'.")
                self.assertIn("data_type", snap, "Snapshot dict should contain key 'data_type'.")
                self.assertIn("value", snap, "Snapshot dict should contain key 'value'.")
                print(f"✅ Azure SQL Market Snapshots integration succeeded! Retrieved {len(snapshots)} latest snapshots.")
            else:
                print("ℹ️ Azure SQL Market Snapshots table is empty, but query executed successfully.")
        except Exception as e:
            self.fail(f"Failed to query market_snapshots from Azure SQL: {e}")

    def test_supabase_vector_search(self) -> None:
        """Test Supabase pgvector cosine similarity search using mock embedding vector."""
        # Generate 1024-dimensional mock embedding vector (all ones)
        mock_embedding = [0.01] * 1024
        try:
            results = search_similar_personas_db(mock_embedding, top_k=2)
            self.assertIsInstance(results, list, "Results should be a list.")
            if len(results) > 0:
                res = results[0]
                self.assertIn("azure_user_uuid", res, "Result dict should contain 'azure_user_uuid'.")
                self.assertIn("similarity", res, "Result dict should contain 'similarity'.")
                
                # Verify that we can query the twin user from Azure SQL using the matched UUID
                uuid = res["azure_user_uuid"]
                profile = get_user_by_uuid(uuid)
                self.assertIsNotNone(profile, f"User profile for UUID '{uuid}' must exist in Azure SQL.")
                self.assertEqual(profile["uuid"], uuid)
                print(f"✅ Supabase Vector Search & Azure SQL user profile join succeeded! Match 1 UUID: {uuid}")
            else:
                print("ℹ️ Supabase pgvector search returned no matches. (Database might be empty).")
        except Exception as e:
            self.fail(f"Failed to perform Supabase pgvector search or Azure SQL join: {e}")

    def test_end_to_end_adviser_flow(self) -> None:
        """Test MidasAdviser RAG recommendation generation."""
        if not os.environ.get("NVIDIA_API_KEY"):
            self.skipTest("Skipping end-to-end LLM adviser test: NVIDIA_API_KEY is not set.")
            
        try:
            adviser = MidasAdviser()
            query = "30대 직장인 주식 부동산 투자 성향"
            report = adviser.get_recommendation(query, top_k=2)
            self.assertIsNotNone(report, "Adviser must return a non-empty report string.")
            self.assertIn("요약", report, "Report should contain section '요약'.")
            self.assertIn("포트폴리오", report, "Report should contain section '포트폴리오'.")
            self.assertIn("세금", report, "Report should contain section '세금'.")
            print("✅ End-to-End MidasAdviser hybrid RAG recommendation generation succeeded!")
            
            # Print a snippet of the report for visual reference in logs
            print("\n----- Report Snippet -----")
            print("\n".join(report.splitlines()[:15]) + "\n...")
            print("--------------------------\n")
        except Exception as e:
            self.fail(f"End-to-End MidasAdviser flow failed: {e}")


if __name__ == "__main__":
    unittest.main()
