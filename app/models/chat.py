"""
Pydantic models for chat functionality
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatSession(BaseModel):
    """Model for a chat session"""
    session_id: str = Field(..., description="Unique session identifier")
    title: str = Field(default="New Conversation", description="Session title")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    last_updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "title": "Resume Search Session",
                "created_at": "2026-01-12 10:30:00",
                "last_updated_at": "2026-01-12 11:45:00"
            }
        }


class ChatMessage(BaseModel):
    """Model for a chat message"""
    message_id: str = Field(..., description="Unique message identifier")
    session_id: str = Field(..., description="Parent session ID")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")
    candidate_ids: Optional[List[str]] = Field(default_factory=list, description="Referenced candidate IDs")
    candidate_names: Optional[List[dict]] = Field(default_factory=list, description="Referenced candidates with names")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_xyz789",
                "session_id": "session_abc123",
                "role": "assistant",
                "content": "Here are the projects for Rosy Yuniar...",
                "timestamp": "2026-01-12 10:35:00",
                "candidate_ids": ["abc-123"],
                "candidate_names": [{"id": "abc-123", "name": "Rosy Yuniar"}]
            }
        }


class MessageResult(BaseModel):
    """Model for message-candidate associations"""
    message_id: str = Field(..., description="Parent message ID")
    candidate_id: str = Field(..., description="Associated candidate ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_xyz789",
                "candidate_id": "abc-123"
            }
        }


class ChatHistoryItem(BaseModel):
    """Model for chat history items used in agent context"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    candidate_ids: Optional[List[str]] = Field(default_factory=list, description="Referenced candidate IDs")
    candidate_names: Optional[List[dict]] = Field(default_factory=list, description="Referenced candidates with names")
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "assistant",
                "content": "Rosy Yuniar has 3 years of experience...",
                "candidate_ids": ["abc-123"],
                "candidate_names": [{"id": "abc-123", "name": "Rosy Yuniar"}]
            }
        }
