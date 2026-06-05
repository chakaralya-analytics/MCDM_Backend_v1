from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from .models import AHPProject
import json

class AHPAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
    
    def test_criteria_calculation_success(self):
        """Test successful criteria calculation"""
        data = {
            'project_name': 'Test Project',
            'criteria': ['Cost', 'Quality'],
            'pairwise_matrix': [[1.0, 2.0], [0.5, 1.0]]
        }
        response = self.client.post('/api/calculate/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['project_type'], 'criteria_only')
    
    def test_invalid_matrix_validation(self):
        """Test matrix validation"""
        data = {
            'project_name': 'Test Project',
            'criteria': ['Cost', 'Quality'],
            'pairwise_matrix': [[1.0, 2.0], [0.5, 2.0]]  # Invalid - not reciprocal
        }
        response = self.client.post('/api/calculate/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_alternative_calculation_workflow(self):
        """Test complete workflow"""
        # Create criteria project
        project = AHPProject.objects.create(
            user=self.user,
            project_name='Test Project',
            project_type='criteria_only',
            criteria=['Cost', 'Quality'],
            pairwise_matrix=[[1.0, 2.0], [0.5, 1.0]],
            weights=[0.6667, 0.3333],
            consistency_ratio=0.0
        )
        
        # Add alternatives
        data = {
            'id': project.id,
            'alternatives': ['Option A', 'Option B'],
            'alternative_matrices': [
                [[1.0, 2.0], [0.5, 1.0]],
                [[1.0, 0.5], [2.0, 1.0]]
            ]
        }
        response = self.client.post('/api/calculate_alternatives/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify project was updated
        project.refresh_from_db()
        self.assertEqual(project.project_type, 'full_analysis')
    
    def test_unauthorized_access(self):
        """Test API without authentication"""
        self.client.credentials()  # Remove auth
        response = self.client.get('/api/projects/criteria-only/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)