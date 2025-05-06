from django.db import models

# Create your models here.

class SearchQuery(models.Model):
    """Model to store search queries for analytics or advanced search features."""
    query_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    # Add other fields as needed
