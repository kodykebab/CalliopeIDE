"""Project metadata model for storing project information"""
from datetime import datetime
from server.middleware.database import db


class ProjectMetadata(db.Model):
    """Project metadata model for storing project information"""
    
    __tablename__ = 'project_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    project_name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    project_type = db.Column(db.String(50), nullable=True, index=True)  # 'smart_contract', 'web_app', etc.
    language = db.Column(db.String(50), nullable=True)  # 'solidity', 'python', 'javascript', etc.
    framework = db.Column(db.String(100), nullable=True)  # 'hardhat', 'truffle', 'react', etc.
    
    # File system information
    project_path = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('projects', lazy=True, cascade='all, delete-orphan'))
    
    def __init__(self, user_id, project_name, description=None, project_type=None, language=None, framework=None, project_path=None):
        self.user_id = user_id
        self.project_name = project_name
        self.description = description
        self.project_type = project_type
        self.language = language
        self.framework = framework
        self.project_path = project_path
        self.is_active = True
    
    def update_last_accessed(self):
        """Update the last accessed timestamp"""
        self.last_accessed = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def deactivate(self):
        """Mark project as inactive"""
        self.is_active = False
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def get_user_projects(user_id, active_only=True):
        """Get all projects for a user"""
        query = ProjectMetadata.query.filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(ProjectMetadata.updated_at.desc()).all()
    
    @staticmethod
    def get_project_by_name(user_id, project_name):
        """Get a specific project by name for a user"""
        return ProjectMetadata.query.filter_by(
            user_id=user_id, 
            project_name=project_name, 
            is_active=True
        ).first()
    
    def to_dict(self, include_path=False):
        """Convert project metadata object to dictionary"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'project_name': self.project_name,
            'description': self.description,
            'project_type': self.project_type,
            'language': self.language,
            'framework': self.framework,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None
        }
        if include_path:
            data['project_path'] = self.project_path
        return data
    
    def __repr__(self):
        return f'<ProjectMetadata {self.id}: {self.project_name} for User {self.user_id}>'