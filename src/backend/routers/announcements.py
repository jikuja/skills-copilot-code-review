"""
Endpoints for managing announcements in the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson.objectid import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_announcements(active_only: bool = Query(True)) -> List[Dict[str, Any]]:
    """
    Get all announcements, optionally filtered to show only active ones.
    
    - active_only: If True, only returns announcements that are currently valid
      (start_date has passed and expiration_date hasn't)
    """
    now = datetime.utcnow()
    query = {}
    
    if active_only:
        query = {
            "$and": [
                {"start_date": {"$lte": now}},
                {"expiration_date": {"$gt": now}}
            ]
        }
    
    announcements = []
    for announcement in announcements_collection.find(query).sort("created_at", -1):
        announcement["_id"] = str(announcement["_id"])
        # Convert datetime objects to ISO format strings
        if "start_date" in announcement:
            announcement["start_date"] = announcement["start_date"].isoformat()
        if "expiration_date" in announcement:
            announcement["expiration_date"] = announcement["expiration_date"].isoformat()
        if "created_at" in announcement:
            announcement["created_at"] = announcement["created_at"].isoformat()
        announcements.append(announcement)
    
    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    title: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Create a new announcement. Requires teacher authentication.
    
    - title: Title of the announcement
    - message: Content of the announcement
    - expiration_date: When the announcement expires (ISO format datetime string)
    - start_date: When the announcement becomes active (ISO format datetime string, optional)
    - teacher_username: Username of the authenticated teacher (required)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    try:
        # Parse dates
        exp_date = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
        start = None
        if start_date:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            # If no start date provided, start immediately
            start = datetime.utcnow()

        # Validate expiration date is in the future
        if exp_date <= datetime.utcnow():
            raise HTTPException(
                status_code=400, detail="Expiration date must be in the future")

        # Validate start date is before expiration date
        if start >= exp_date:
            raise HTTPException(
                status_code=400, detail="Start date must be before expiration date")

        # Create announcement
        announcement = {
            "_id": ObjectId(),
            "title": title,
            "message": message,
            "start_date": start,
            "expiration_date": exp_date,
            "created_at": datetime.utcnow(),
            "created_by": teacher_username
        }

        result = announcements_collection.insert_one(announcement)

        # Return the created announcement
        announcement["_id"] = str(result.inserted_id)
        announcement["start_date"] = announcement["start_date"].isoformat()
        announcement["expiration_date"] = announcement["expiration_date"].isoformat()
        announcement["created_at"] = announcement["created_at"].isoformat()

        return announcement

    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid date format: {str(e)}")


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    title: Optional[str] = None,
    message: Optional[str] = None,
    expiration_date: Optional[str] = None,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Update an announcement. Requires teacher authentication.
    
    - announcement_id: ID of the announcement to update
    - title: New title (optional)
    - message: New message (optional)
    - expiration_date: New expiration date (optional, ISO format)
    - start_date: New start date (optional, ISO format)
    - teacher_username: Username of the authenticated teacher (required)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    try:
        # Find the announcement
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid announcement ID format")

        announcement = announcements_collection.find_one({"_id": obj_id})
        if not announcement:
            raise HTTPException(
                status_code=404, detail="Announcement not found")

        # Build update dictionary
        update_dict = {}
        
        if title is not None:
            update_dict["title"] = title
        
        if message is not None:
            update_dict["message"] = message
        
        if expiration_date is not None:
            exp_date = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
            
            # Get the start date (use existing or provided)
            if start_date:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                start = announcement.get("start_date", datetime.utcnow())
            
            # Validate expiration date is in the future
            if exp_date <= datetime.utcnow():
                raise HTTPException(
                    status_code=400, detail="Expiration date must be in the future")

            # Validate start date is before expiration date
            if start >= exp_date:
                raise HTTPException(
                    status_code=400, detail="Start date must be before expiration date")
            
            update_dict["expiration_date"] = exp_date
        
        if start_date is not None:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            
            # Get the expiration date (use existing or provided)
            if expiration_date:
                exp_date = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
            else:
                exp_date = announcement.get("expiration_date", datetime.utcnow())
            
            # Validate start date is before expiration date
            if start >= exp_date:
                raise HTTPException(
                    status_code=400, detail="Start date must be before expiration date")
            
            update_dict["start_date"] = start

        if not update_dict:
            raise HTTPException(
                status_code=400, detail="No fields to update")

        # Update the announcement
        result = announcements_collection.update_one(
            {"_id": obj_id},
            {"$set": update_dict}
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500, detail="Failed to update announcement")

        # Return the updated announcement
        updated = announcements_collection.find_one({"_id": obj_id})
        updated["_id"] = str(updated["_id"])
        updated["start_date"] = updated["start_date"].isoformat()
        updated["expiration_date"] = updated["expiration_date"].isoformat()
        updated["created_at"] = updated["created_at"].isoformat()

        return updated

    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid date format: {str(e)}")


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """
    Delete an announcement. Requires teacher authentication.
    
    - announcement_id: ID of the announcement to delete
    - teacher_username: Username of the authenticated teacher (required)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    try:
        # Convert to ObjectId
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid announcement ID format")

        # Delete the announcement
        result = announcements_collection.delete_one({"_id": obj_id})

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, detail="Announcement not found")

        return {"message": "Announcement deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete announcement: {str(e)}")
