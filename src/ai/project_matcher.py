"""
Project Matcher - Matches user input to actual project names/slugs.
"""

import logging
from typing import Optional, Dict, Any
from difflib import SequenceMatcher

from storage import list_projects, load_project, slugify

logger = logging.getLogger(__name__)


class ProjectMatcher:
    """
    Matches user-provided project names to actual projects.
    Uses fuzzy matching to handle variations.
    """
    
    def __init__(self):
        self._projects_cache = None
        self._refresh_cache()
    
    def _refresh_cache(self):
        """Refresh the projects cache."""
        self._projects_cache = list_projects()
    
    def find_project(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Find a project matching the user input.
        
        Args:
            user_input: User-provided project name/identifier
            
        Returns:
            Project dict if found, None otherwise
        """
        self._refresh_cache()
        
        if not self._projects_cache:
            return None
        
        user_lower = user_input.lower().strip()
        user_slug = slugify(user_input)
        
        # Exact match on name
        for project in self._projects_cache:
            if project.get("name", "").lower() == user_lower:
                return project
            if project.get("slug", "") == user_slug:
                return project
        
        # Fuzzy match on name
        best_match = None
        best_score = 0.0
        threshold = 0.6  # Minimum similarity threshold
        
        for project in self._projects_cache:
            name = project.get("name", "").lower()
            slug = project.get("slug", "")
            
            # Check name similarity
            name_score = SequenceMatcher(None, user_lower, name).ratio()
            slug_score = SequenceMatcher(None, user_slug, slug).ratio()
            
            score = max(name_score, slug_score)
            
            # Bonus if user input is contained in name
            if user_lower in name or name in user_lower:
                score += 0.2
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = project
        
        return best_match
    
    def load_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a project blueprint by name (using matching).
        
        Args:
            project_name: Project name to find and load
            
        Returns:
            Blueprint dict if found, None otherwise
        """
        project = self.find_project(project_name)
        if not project:
            return None
        
        slug = project.get("slug")
        if not slug:
            return None
        
        return load_project(slug)
    
    def list_all_projects(self) -> list[Dict[str, Any]]:
        """
        Get list of all projects.
        
        Returns:
            List of project dicts
        """
        self._refresh_cache()
        return self._projects_cache or []
