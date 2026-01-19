"""Privacy-preserving data anonymization via variable substitution."""

from __future__ import annotations

import re
import json
import logging
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass

from app.core.redis_client import RedisClient

logger = logging.getLogger(__name__)

# Redis key prefix for privacy mappings
PRIVACY_MAPPING_PREFIX = "pockitect:privacy:mapping"
PRIVACY_MAPPING_TTL = 86400  # 24 hours


@dataclass
class AnonymizationMapping:
    """Bidirectional mapping between real IDs and variables."""
    
    real_to_var: Dict[str, str]
    var_to_real: Dict[str, str]
    session_id: str
    
    def get_variable(self, real_id: str) -> str:
        """Get variable for a real ID, creating one if needed."""
        if real_id not in self.real_to_var:
            var_name = self._generate_variable_name(len(self.real_to_var))
            self.real_to_var[real_id] = var_name
            self.var_to_real[var_name] = real_id
        return self.real_to_var[real_id]
    
    def get_real_id(self, variable: str) -> Optional[str]:
        """Get real ID for a variable."""
        return self.var_to_real.get(variable)
    
    def _generate_variable_name(self, index: int) -> str:
        """Generate a deterministic variable name."""
        # Generate type-based prefix from the real ID
        # Extract resource type from common patterns
        base_types = {
            "i-": "INSTANCE",
            "vpc-": "VPC",
            "sg-": "SECURITY_GROUP",
            "subnet-": "SUBNET",
            "rtb-": "ROUTE_TABLE",
            "igw-": "INTERNET_GATEWAY",
            "eipalloc-": "EIP",
            "vol-": "VOLUME",
            "snap-": "SNAPSHOT",
            "ami-": "AMI",
            "arn:aws:": "ARN",
        }
        
        # Try to find type from previous mappings
        for prefix, var_type in base_types.items():
            for real_id in self.real_to_var.keys():
                if real_id.startswith(prefix):
                    return f"{var_type}_VAR_{index + 1}"
        
        # Default fallback
        return f"RESOURCE_VAR_{index + 1}"


class DataAnonymizer:
    """Anonymizes AWS resource identifiers for privacy-preserving cloud API calls."""
    
    # Patterns for AWS resource identifiers
    PATTERNS = {
        "ec2_instance": re.compile(r'\bi-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "vpc": re.compile(r'\bvpc-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "security_group": re.compile(r'\bsg-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "subnet": re.compile(r'\bsubnet-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "route_table": re.compile(r'\brtb-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "internet_gateway": re.compile(r'\bigw-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "eip": re.compile(r'\beipalloc-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "volume": re.compile(r'\bvol-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "snapshot": re.compile(r'\bsnap-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "ami": re.compile(r'\bami-[a-z0-9]{8,17}\b', re.IGNORECASE),
        "arn": re.compile(r'\barn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:[a-z0-9-]+[:\/][a-zA-Z0-9\-_\/\.]+', re.IGNORECASE),
        "account_id": re.compile(r'\b\d{12}\b'),  # 12-digit AWS account ID
        "access_key": re.compile(r'\bAKIA[0-9A-Z]{16}\b', re.IGNORECASE),
    }
    
    def __init__(self, session_id: str):
        """
        Initialize the anonymizer.
        
        Args:
            session_id: Session identifier for mapping storage
        """
        self.session_id = session_id
        self.redis_client = RedisClient()
        self._mapping: Optional[AnonymizationMapping] = None
    
    def _get_mapping_key(self) -> str:
        """Get Redis key for this session's mapping."""
        return f"{PRIVACY_MAPPING_PREFIX}:{self.session_id}"
    
    def _load_mapping(self) -> AnonymizationMapping:
        """Load mapping from Redis or create new one."""
        if self._mapping is not None:
            return self._mapping
        
        try:
            conn = self.redis_client.get_connection()
            key = self._get_mapping_key()
            data = conn.get(key)
            
            if data:
                mapping_data = json.loads(data)
                self._mapping = AnonymizationMapping(
                    real_to_var=mapping_data.get("real_to_var", {}),
                    var_to_real=mapping_data.get("var_to_real", {}),
                    session_id=self.session_id,
                )
            else:
                self._mapping = AnonymizationMapping(
                    real_to_var={},
                    var_to_real={},
                    session_id=self.session_id,
                )
        except Exception as e:
            logger.warning(f"Failed to load mapping from Redis: {e}")
            self._mapping = AnonymizationMapping(
                real_to_var={},
                var_to_real={},
                session_id=self.session_id,
            )
        
        return self._mapping
    
    def _save_mapping(self) -> None:
        """Save mapping to Redis with TTL."""
        if self._mapping is None:
            return
        
        try:
            conn = self.redis_client.get_connection()
            key = self._get_mapping_key()
            data = json.dumps({
                "real_to_var": self._mapping.real_to_var,
                "var_to_real": self._mapping.var_to_real,
            })
            conn.setex(key, PRIVACY_MAPPING_TTL, data)
        except Exception as e:
            logger.warning(f"Failed to save mapping to Redis: {e}")
    
    def _extract_identifiers(self, data: Any) -> Set[str]:
        """
        Extract all AWS resource identifiers from data structure.
        
        Args:
            data: Data structure (dict, list, str) to scan
            
        Returns:
            Set of found identifiers
        """
        identifiers = set()
        
        if isinstance(data, str):
            # Scan string for patterns
            for pattern in self.PATTERNS.values():
                matches = pattern.findall(data)
                identifiers.update(matches)
        elif isinstance(data, dict):
            for key, value in data.items():
                identifiers.update(self._extract_identifiers(value))
        elif isinstance(data, list):
            for item in data:
                identifiers.update(self._extract_identifiers(item))
        
        return identifiers
    
    def anonymize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize AWS resource identifiers in context.
        
        Args:
            context: Context dictionary to anonymize
            
        Returns:
            Anonymized context dictionary
        """
        mapping = self._load_mapping()
        
        # First pass: extract all identifiers
        identifiers = self._extract_identifiers(context)
        
        # Second pass: create mappings for all identifiers
        for identifier in identifiers:
            mapping.get_variable(identifier)
        
        # Save mapping
        self._save_mapping()
        
        # Third pass: substitute identifiers
        anonymized = self._substitute_identifiers(context, mapping)
        
        return anonymized
    
    def _substitute_identifiers(self, data: Any, mapping: AnonymizationMapping) -> Any:
        """Recursively substitute identifiers in data structure."""
        if isinstance(data, str):
            result = data
            for real_id, variable in mapping.real_to_var.items():
                # Use word boundaries for substitution
                pattern = re.compile(r'\b' + re.escape(real_id) + r'\b', re.IGNORECASE)
                result = pattern.sub(variable, result)
            return result
        elif isinstance(data, dict):
            return {
                key: self._substitute_identifiers(value, mapping)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [
                self._substitute_identifiers(item, mapping)
                for item in data
            ]
        else:
            return data
    
    def deanonymize_response(self, response: str) -> str:
        """
        De-anonymize response text by reversing variable substitutions.
        
        Args:
            response: Anonymized response text
            
        Returns:
            De-anonymized response text
        """
        mapping = self._load_mapping()
        
        if not mapping.var_to_real:
            return response
        
        result = response
        for variable, real_id in mapping.var_to_real.items():
            pattern = re.compile(r'\b' + re.escape(variable) + r'\b')
            result = pattern.sub(real_id, result)
        
        return result
    
    def clear_mapping(self) -> None:
        """Clear the mapping for this session."""
        try:
            conn = self.redis_client.get_connection()
            key = self._get_mapping_key()
            conn.delete(key)
            self._mapping = None
        except Exception as e:
            logger.warning(f"Failed to clear mapping: {e}")
