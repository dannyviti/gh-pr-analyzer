"""
Unit tests for reviewer workload analysis functionality.

This module contains comprehensive tests for the ReviewerWorkloadAnalyzer class,
covering all methods, edge cases, and error handling scenarios.
"""

import unittest
from unittest.mock import patch, MagicMock
import pytest
from datetime import datetime

from reviewer_analyzer import ReviewerWorkloadAnalyzer


class TestReviewerWorkloadAnalyzer(unittest.TestCase):
    """Test cases for the ReviewerWorkloadAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = ReviewerWorkloadAnalyzer(default_threshold=10)
        
        # Sample PR data for testing
        self.sample_prs = [
            {
                'number': 123,
                'created_at': '2023-01-01T10:00:00Z',
                'requested_reviewers': [
                    {'login': 'alice', 'name': 'Alice Johnson'},
                    {'login': 'bob', 'name': 'Bob Smith'}
                ],
                'requested_teams': [
                    {'name': 'core-team', 'slug': 'core-team'}
                ]
            },
            {
                'number': 124,
                'created_at': '2023-01-02T10:00:00Z',
                'requested_reviewers': [
                    {'login': 'alice', 'name': 'Alice Johnson'},
                    {'login': 'charlie', 'name': 'Charlie Brown'}
                ],
                'requested_teams': []
            },
            {
                'number': 125,
                'created_at': '2023-01-03T10:00:00Z',
                'requested_reviewers': [
                    {'login': 'alice', 'name': 'Alice Johnson'}
                ],
                'requested_teams': [
                    {'name': 'frontend-team', 'slug': 'frontend-team'}
                ]
            }
        ]
    
    def test_initialization(self):
        """Test ReviewerWorkloadAnalyzer initialization."""
        analyzer = ReviewerWorkloadAnalyzer(default_threshold=15)
        
        self.assertEqual(analyzer.default_threshold, 15)
        self.assertEqual(analyzer._reviewer_data, {})
        self.assertEqual(analyzer._analysis_metadata, {})
        
        # Test default threshold
        default_analyzer = ReviewerWorkloadAnalyzer()
        self.assertEqual(default_analyzer.default_threshold, 10)
    
    def test_aggregate_reviewer_requests_basic(self):
        """Test basic reviewer request aggregation."""
        result = self.analyzer.aggregate_reviewer_requests(self.sample_prs, include_teams=False)
        
        # Check that we have the expected reviewers
        self.assertIn('alice', result)
        self.assertIn('bob', result)
        self.assertIn('charlie', result)
        
        # Check Alice's data (should have 3 requests)
        alice_data = result['alice']
        self.assertEqual(alice_data['login'], 'alice')
        self.assertEqual(alice_data['name'], 'Alice Johnson')
        self.assertEqual(alice_data['total_requests'], 3)
        self.assertEqual(set(alice_data['pr_numbers']), {123, 124, 125})
        self.assertEqual(alice_data['request_sources'], ['individual', 'individual', 'individual'])
        
        # Check Bob's data (should have 1 request)
        bob_data = result['bob']
        self.assertEqual(bob_data['total_requests'], 1)
        self.assertEqual(bob_data['pr_numbers'], [123])
        
        # Check Charlie's data (should have 1 request)
        charlie_data = result['charlie']
        self.assertEqual(charlie_data['total_requests'], 1)
        self.assertEqual(charlie_data['pr_numbers'], [124])
    
    def test_aggregate_reviewer_requests_with_teams(self):
        """Test reviewer request aggregation including teams."""
        result = self.analyzer.aggregate_reviewer_requests(self.sample_prs, include_teams=True)
        
        # Should include individual reviewers and teams
        self.assertIn('alice', result)
        self.assertIn('bob', result)
        self.assertIn('charlie', result)
        self.assertIn('team:core-team', result)
        self.assertIn('team:frontend-team', result)
        
        # Check team data
        core_team_data = result['team:core-team']
        self.assertEqual(core_team_data['login'], 'team:core-team')
        self.assertEqual(core_team_data['name'], 'Team: core-team')
        self.assertEqual(core_team_data['total_requests'], 1)
        self.assertEqual(core_team_data['pr_numbers'], [123])
        
        frontend_team_data = result['team:frontend-team']
        self.assertEqual(frontend_team_data['total_requests'], 1)
        self.assertEqual(frontend_team_data['pr_numbers'], [125])
    
    def test_aggregate_reviewer_requests_empty_input(self):
        """Test aggregation with empty PR list."""
        result = self.analyzer.aggregate_reviewer_requests([])
        
        self.assertEqual(result, {})
    
    def test_aggregate_reviewer_requests_malformed_data(self):
        """Test aggregation with malformed PR data."""
        malformed_prs = [
            {
                'number': 126,
                'created_at': '2023-01-04T10:00:00Z',
                'requested_reviewers': 'not_a_list',  # Invalid data type
                'requested_teams': [
                    {'name': 'valid-team', 'slug': 'valid-team'}
                ]
            },
            {
                # Missing number field
                'created_at': '2023-01-05T10:00:00Z',
                'requested_reviewers': [
                    {'login': 'valid_user', 'name': 'Valid User'}
                ]
            },
            {
                'number': 127,
                'requested_reviewers': [
                    {'login': 'good_user'},
                    {'name': 'Missing Login'},  # Missing login field
                    {}  # Empty reviewer object
                ]
            }
        ]
        
        result = self.analyzer.aggregate_reviewer_requests(malformed_prs, include_teams=True)
        
        # Should only include valid data
        self.assertIn('team:valid-team', result)
        self.assertIn('good_user', result)
        
        # Should handle missing login gracefully
        self.assertNotIn('Missing Login', result)
        self.assertNotIn('', result)
        
        # Verify valid data is processed correctly
        self.assertEqual(result['good_user']['total_requests'], 1)
        self.assertEqual(result['team:valid-team']['total_requests'], 1)
    
    def test_detect_reviewer_overload_default_threshold(self):
        """Test overload detection with default threshold."""
        # Create reviewer data with various request counts
        reviewer_data = {
            'overloaded_user': {'total_requests': 15},
            'high_user': {'total_requests': 8},
            'normal_user1': {'total_requests': 5},
            'normal_user2': {'total_requests': 2}
        }
        
        result = self.analyzer.detect_reviewer_overload(reviewer_data)
        
        self.assertEqual(result['OVERLOADED'], ['overloaded_user'])
        self.assertEqual(result['HIGH'], ['high_user'])  # 8 >= 7.5 (75% of 10)
        self.assertEqual(set(result['NORMAL']), {'normal_user1', 'normal_user2'})
    
    def test_detect_reviewer_overload_custom_threshold(self):
        """Test overload detection with custom threshold."""
        reviewer_data = {
            'user1': {'total_requests': 20},
            'user2': {'total_requests': 15},
            'user3': {'total_requests': 10},
            'user4': {'total_requests': 5}
        }
        
        result = self.analyzer.detect_reviewer_overload(reviewer_data, threshold=16)
        
        self.assertEqual(result['OVERLOADED'], ['user1'])
        self.assertEqual(result['HIGH'], ['user2'])  # 15 >= 12 (75% of 16)
        self.assertEqual(set(result['NORMAL']), {'user3', 'user4'})
    
    def test_detect_reviewer_overload_empty_data(self):
        """Test overload detection with empty data."""
        result = self.analyzer.detect_reviewer_overload({})
        
        self.assertEqual(result['OVERLOADED'], [])
        self.assertEqual(result['HIGH'], [])
        self.assertEqual(result['NORMAL'], [])
    
    def test_calculate_reviewer_statistics_basic(self):
        """Test basic statistical calculations."""
        reviewer_data = {
            'user1': {'total_requests': 10},
            'user2': {'total_requests': 20},
            'user3': {'total_requests': 30},
            'user4': {'total_requests': 40}
        }
        
        stats = self.analyzer.calculate_reviewer_statistics(reviewer_data)
        
        self.assertEqual(stats['total_reviewers'], 4)
        self.assertEqual(stats['total_requests'], 100)
        self.assertEqual(stats['mean_requests'], 25.0)
        self.assertEqual(stats['median_requests'], 25.0)
        self.assertEqual(stats['min_requests'], 10)
        self.assertEqual(stats['max_requests'], 40)
        self.assertGreater(stats['std_dev_requests'], 0)
    
    def test_calculate_reviewer_statistics_single_reviewer(self):
        """Test statistics with single reviewer (edge case)."""
        reviewer_data = {
            'user1': {'total_requests': 15}
        }
        
        stats = self.analyzer.calculate_reviewer_statistics(reviewer_data)
        
        self.assertEqual(stats['total_reviewers'], 1)
        self.assertEqual(stats['total_requests'], 15)
        self.assertEqual(stats['mean_requests'], 15.0)
        self.assertEqual(stats['median_requests'], 15.0)
        self.assertEqual(stats['std_dev_requests'], 0.0)  # No deviation with single point
        self.assertEqual(stats['min_requests'], 15)
        self.assertEqual(stats['max_requests'], 15)
    
    def test_calculate_reviewer_statistics_empty_data(self):
        """Test statistics with empty data."""
        stats = self.analyzer.calculate_reviewer_statistics({})
        
        expected_stats = {
            'total_reviewers': 0,
            'total_requests': 0,
            'mean_requests': 0.0,
            'median_requests': 0.0,
            'std_dev_requests': 0.0,
            'min_requests': 0,
            'max_requests': 0,
            'percentile_75': 0.0,
            'percentile_90': 0.0,
            'percentile_95': 0.0
        }
        
        self.assertEqual(stats, expected_stats)
    
    def test_percentile_calculation(self):
        """Test percentile calculation method."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        # Test various percentiles
        self.assertEqual(self.analyzer._calculate_percentile(data, 50), 5.5)  # Median
        self.assertEqual(self.analyzer._calculate_percentile(data, 75), 7.75)
        self.assertEqual(self.analyzer._calculate_percentile(data, 90), 9.1)
        self.assertEqual(self.analyzer._calculate_percentile(data, 100), 10)
        
        # Test edge cases
        self.assertEqual(self.analyzer._calculate_percentile([], 50), 0.0)
        self.assertEqual(self.analyzer._calculate_percentile([5], 75), 5)
        self.assertEqual(self.analyzer._calculate_percentile([1, 2], 50), 1.5)
    
    def test_analyze_reviewer_distribution_basic(self):
        """Test basic distribution analysis."""
        # Create reviewer data with clear distribution pattern
        reviewer_data = {
            'top_reviewer': {'total_requests': 100, 'name': 'Top Reviewer'},
            'high_reviewer': {'total_requests': 50, 'name': 'High Reviewer'},
            'med_reviewer': {'total_requests': 20, 'name': 'Med Reviewer'},
            'low_reviewer1': {'total_requests': 5, 'name': 'Low Reviewer 1'},
            'low_reviewer2': {'total_requests': 1, 'name': 'Low Reviewer 2'}
        }
        
        analysis = self.analyzer.analyze_reviewer_distribution(reviewer_data)
        
        # Check top reviewers (should be sorted by request count)
        top_reviewers = analysis['top_reviewers']
        self.assertEqual(len(top_reviewers), 5)  # All 5 reviewers since < 10
        self.assertEqual(top_reviewers[0]['login'], 'top_reviewer')
        self.assertEqual(top_reviewers[0]['total_requests'], 100)
        self.assertEqual(top_reviewers[1]['login'], 'high_reviewer')
        
        # Check concentration ratio (top 20% should handle most requests)
        self.assertGreater(analysis['concentration_ratio'], 0.5)  # Top reviewer handles >50%
        
        # Check Gini coefficient (should indicate inequality)
        self.assertGreater(analysis['gini_coefficient'], 0.5)
        
        # Check diversity score
        self.assertLessEqual(analysis['reviewer_diversity_score'], 1.0)
        self.assertGreaterEqual(analysis['reviewer_diversity_score'], 0.0)
        
        # Check underutilized reviewers
        self.assertGreater(len(analysis['underutilized_reviewers']), 0)
    
    def test_analyze_reviewer_distribution_empty_data(self):
        """Test distribution analysis with empty data."""
        analysis = self.analyzer.analyze_reviewer_distribution({})
        
        expected = {
            'concentration_ratio': 0.0,
            'gini_coefficient': 0.0,
            'top_reviewers': [],
            'underutilized_reviewers': [],
            'reviewer_diversity_score': 0.0
        }
        
        self.assertEqual(analysis, expected)
    
    def test_gini_coefficient_calculation(self):
        """Test Gini coefficient calculation accuracy."""
        # Perfect equality: all values equal
        equal_values = [10, 10, 10, 10, 10]
        gini_equal = self.analyzer._calculate_gini_coefficient(equal_values)
        self.assertAlmostEqual(gini_equal, 0.0, places=3)
        
        # Maximum inequality: one person has everything
        max_inequality = [0, 0, 0, 0, 100]
        gini_max = self.analyzer._calculate_gini_coefficient(max_inequality)
        self.assertGreater(gini_max, 0.7)  # Should be high inequality
        
        # Moderate inequality
        moderate = [10, 20, 30, 40, 50]
        gini_moderate = self.analyzer._calculate_gini_coefficient(moderate)
        self.assertGreater(gini_moderate, 0.0)
        self.assertLess(gini_moderate, gini_max)
        
        # Edge cases
        self.assertEqual(self.analyzer._calculate_gini_coefficient([]), 0.0)
        self.assertEqual(self.analyzer._calculate_gini_coefficient([10]), 0.0)
        self.assertEqual(self.analyzer._calculate_gini_coefficient([0, 0, 0]), 0.0)
    
    def test_get_reviewer_workload_summary(self):
        """Test comprehensive workload summary generation."""
        summary = self.analyzer.get_reviewer_workload_summary(
            self.sample_prs,
            threshold=5,
            include_teams=True,
            org_name='testorg'
        )
        
        # Check that all expected sections are present
        self.assertIn('metadata', summary)
        self.assertIn('reviewer_data', summary)
        self.assertIn('statistics', summary)
        self.assertIn('overload_analysis', summary)
        self.assertIn('distribution_analysis', summary)
        
        # Check metadata
        metadata = summary['metadata']
        self.assertEqual(metadata['total_prs_analyzed'], 3)
        self.assertEqual(metadata['include_teams'], True)
        self.assertEqual(metadata['overload_threshold'], 5)
        self.assertEqual(metadata['org_name'], 'testorg')
        self.assertIn('analysis_date', metadata)
        
        # Check that reviewer data exists
        self.assertGreater(len(summary['reviewer_data']), 0)
        
        # Check that statistics are calculated
        stats = summary['statistics']
        self.assertGreater(stats['total_reviewers'], 0)
        self.assertGreater(stats['total_requests'], 0)
        
        # Check overload analysis
        overload = summary['overload_analysis']
        self.assertIn('OVERLOADED', overload)
        self.assertIn('HIGH', overload)
        self.assertIn('NORMAL', overload)
        
        # Check distribution analysis
        distribution = summary['distribution_analysis']
        self.assertIn('concentration_ratio', distribution)
        self.assertIn('top_reviewers', distribution)
    
    def test_date_range_tracking(self):
        """Test that date ranges are properly tracked in aggregation."""
        prs_with_dates = [
            {
                'number': 1,
                'created_at': '2023-01-01T10:00:00Z',
                'requested_reviewers': [{'login': 'user1', 'name': 'User 1'}]
            },
            {
                'number': 2,
                'created_at': '2023-01-15T10:00:00Z',
                'requested_reviewers': [{'login': 'user1', 'name': 'User 1'}]
            },
            {
                'number': 3,
                'created_at': '2023-02-01T10:00:00Z',
                'requested_reviewers': [{'login': 'user1', 'name': 'User 1'}]
            }
        ]
        
        result = self.analyzer.aggregate_reviewer_requests(prs_with_dates, include_teams=False)
        
        user1_data = result['user1']
        self.assertEqual(user1_data['first_request_date'], '2023-01-01T10:00:00Z')
        self.assertEqual(user1_data['last_request_date'], '2023-02-01T10:00:00Z')
        self.assertEqual(user1_data['total_requests'], 3)
    
    def test_duplicate_pr_handling(self):
        """Test that duplicate PR numbers are handled correctly."""
        prs_with_duplicates = [
            {
                'number': 1,
                'created_at': '2023-01-01T10:00:00Z',
                'requested_reviewers': [{'login': 'user1', 'name': 'User 1'}]
            },
            {
                'number': 1,  # Duplicate PR number
                'created_at': '2023-01-01T10:00:00Z',
                'requested_reviewers': [{'login': 'user1', 'name': 'User 1'}]
            }
        ]
        
        result = self.analyzer.aggregate_reviewer_requests(prs_with_duplicates, include_teams=False)
        
        user1_data = result['user1']
        # Should count as 2 requests but only 1 unique PR
        self.assertEqual(user1_data['total_requests'], 2)
        self.assertEqual(len(user1_data['pr_numbers']), 1)  # Duplicates removed
        self.assertEqual(user1_data['pr_numbers'], [1])


class TestReviewerAnalyzerIntegration(unittest.TestCase):
    """Integration tests for reviewer analyzer with realistic data."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.analyzer = ReviewerWorkloadAnalyzer(default_threshold=20)
        
        # Create realistic PR dataset
        self.realistic_prs = []
        
        # Generate 50 PRs with various reviewer patterns
        reviewers = ['alice', 'bob', 'charlie', 'diana', 'eve', 'frank', 'grace', 'henry']
        teams = [
            {'name': 'frontend', 'slug': 'frontend'},
            {'name': 'backend', 'slug': 'backend'},
            {'name': 'devops', 'slug': 'devops'}
        ]
        
        for i in range(1, 51):
            pr = {
                'number': i,
                'created_at': f'2023-01-{(i % 30) + 1:02d}T10:00:00Z',
                'requested_reviewers': [],
                'requested_teams': []
            }
            
            # Simulate different reviewer request patterns
            if i <= 20:
                # Alice is heavily requested (overloaded pattern)
                pr['requested_reviewers'].append({'login': 'alice', 'name': 'Alice Johnson'})
                
                # Add secondary reviewers occasionally
                if i % 3 == 0:
                    pr['requested_reviewers'].append({'login': 'bob', 'name': 'Bob Smith'})
                
            elif i <= 30:
                # Bob and Charlie share some load
                if i % 2 == 0:
                    pr['requested_reviewers'].append({'login': 'bob', 'name': 'Bob Smith'})
                else:
                    pr['requested_reviewers'].append({'login': 'charlie', 'name': 'Charlie Brown'})
            
            elif i <= 40:
                # Diana and Eve get moderate requests
                if i % 3 == 0:
                    pr['requested_reviewers'].append({'login': 'diana', 'name': 'Diana Prince'})
                if i % 4 == 0:
                    pr['requested_reviewers'].append({'login': 'eve', 'name': 'Eve Adams'})
            
            else:
                # Remaining reviewers get few requests
                reviewer = reviewers[i % len(reviewers)]
                pr['requested_reviewers'].append({'login': reviewer, 'name': f'{reviewer.title()} LastName'})
            
            # Add team requests occasionally
            if i % 10 == 0:
                pr['requested_teams'].append(teams[i % len(teams)])
            
            self.realistic_prs.append(pr)
    
    def test_realistic_workload_analysis(self):
        """Test analysis with realistic PR data."""
        summary = self.analyzer.get_reviewer_workload_summary(
            self.realistic_prs,
            threshold=15,
            include_teams=True,
            org_name='testorg'
        )
        
        # Verify analysis structure
        self.assertIn('reviewer_data', summary)
        self.assertIn('statistics', summary)
        self.assertIn('overload_analysis', summary)
        self.assertIn('distribution_analysis', summary)
        
        reviewer_data = summary['reviewer_data']
        
        # Alice should be the most requested reviewer
        alice_requests = reviewer_data.get('alice', {}).get('total_requests', 0)
        self.assertGreater(alice_requests, 15)  # Should be overloaded
        
        # Verify overload detection works
        overload_analysis = summary['overload_analysis']
        self.assertIn('alice', overload_analysis['OVERLOADED'])
        
        # Check distribution analysis identifies concentration
        distribution = summary['distribution_analysis']
        self.assertGreater(distribution['concentration_ratio'], 0.3)  # Some concentration expected
        
        # Verify statistics are reasonable  
        stats = summary['statistics']
        metadata = summary['metadata']
        self.assertEqual(metadata['total_prs_analyzed'], 50)
        self.assertGreater(stats['mean_requests'], 0)
        self.assertGreater(stats['max_requests'], stats['mean_requests'])
    
    def test_performance_with_large_dataset(self):
        """Test analyzer performance with larger dataset."""
        # Create a larger dataset (500 PRs)
        large_dataset = []
        for i in range(500):
            pr = {
                'number': i,
                'created_at': f'2023-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T10:00:00Z',
                'requested_reviewers': [
                    {'login': f'user_{i % 20}', 'name': f'User {i % 20}'}
                ],
                'requested_teams': []
            }
            large_dataset.append(pr)
        
        # Should complete without errors or excessive time
        import time
        start_time = time.time()
        
        summary = self.analyzer.get_reviewer_workload_summary(large_dataset)
        
        end_time = time.time()
        analysis_time = end_time - start_time
        
        # Should complete in reasonable time (< 5 seconds)
        self.assertLess(analysis_time, 5.0)
        
        # Should process all data correctly
        self.assertEqual(summary['metadata']['total_prs_analyzed'], 500)
        self.assertEqual(len(summary['reviewer_data']), 20)  # 20 unique users


if __name__ == '__main__':
    unittest.main()
