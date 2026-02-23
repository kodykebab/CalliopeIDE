"""Project metadata routes for managing project information"""
from flask import Blueprint, request, jsonify
from server.models import ProjectMetadata
from server.middleware.database import db
from server.utils.auth_utils import token_required
from server.utils.db_utils import create_project_metadata, update_project_metadata
from server.utils.validators import sanitize_input

project_bp = Blueprint('project', __name__, url_prefix='/api/projects')


@project_bp.route('/', methods=['POST'])
@token_required
def create_project(current_user):
    """Create a new project"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Required fields
        project_name = data.get('project_name')
        if not project_name:
            return jsonify({'success': False, 'error': 'Project name is required'}), 400
        
        # Sanitize and validate inputs
        project_name = sanitize_input(project_name, 255)
        description = sanitize_input(data.get('description', ''), 1000) or None
        project_type = sanitize_input(data.get('project_type', ''), 50) or None
        language = sanitize_input(data.get('language', ''), 50) or None
        framework = sanitize_input(data.get('framework', ''), 100) or None
        project_path = sanitize_input(data.get('project_path', ''), 500) or None
        
        # Create project
        project = create_project_metadata(
            user_id=current_user.id,
            project_name=project_name,
            description=description,
            project_type=project_type,
            language=language,
            framework=framework,
            project_path=project_path
        )
        
        return jsonify({
            'success': True,
            'message': 'Project created successfully',
            'project': project.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"Create project error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while creating the project'}), 500


@project_bp.route('/', methods=['GET'])
@project_bp.route('/list', methods=['GET'])
@token_required
def list_projects(current_user):
    """List all projects for the current user"""
    try:
        # Get filtering parameters
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        project_type = request.args.get('project_type')
        language = request.args.get('language')
        
        # Build query
        query = ProjectMetadata.query.filter_by(user_id=current_user.id)
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        if project_type:
            query = query.filter_by(project_type=project_type)
            
        if language:
            query = query.filter_by(language=language)
        
        # Order by most recently updated
        projects = query.order_by(ProjectMetadata.updated_at.desc()).all()
        
        return jsonify({
            'success': True,
            'projects': [project.to_dict() for project in projects],
            'total_projects': len(projects),
            'filters': {
                'active_only': active_only,
                'project_type': project_type,
                'language': language
            }
        }), 200
        
    except Exception as e:
        print(f"List projects error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while retrieving projects'}), 500


@project_bp.route('/<int:project_id>', methods=['GET'])
@token_required
def get_project(current_user, project_id):
    """Get a specific project by ID"""
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, 
            user_id=current_user.id
        ).first()
        
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        return jsonify({
            'success': True,
            'project': project.to_dict(include_path=True)
        }), 200
        
    except Exception as e:
        print(f"Get project error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while retrieving the project'}), 500


@project_bp.route('/<int:project_id>', methods=['PUT'])
@token_required
def update_project(current_user, project_id):
    """Update a project"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Sanitize inputs
        update_data = {}
        
        if 'project_name' in data:
            update_data['project_name'] = sanitize_input(data['project_name'], 255)
            
        if 'description' in data:
            update_data['description'] = sanitize_input(data['description'], 1000) or None
            
        if 'project_type' in data:
            update_data['project_type'] = sanitize_input(data['project_type'], 50) or None
            
        if 'language' in data:
            update_data['language'] = sanitize_input(data['language'], 50) or None
            
        if 'framework' in data:
            update_data['framework'] = sanitize_input(data['framework'], 100) or None
            
        if 'project_path' in data:
            update_data['project_path'] = sanitize_input(data['project_path'], 500) or None
        
        if not update_data:
            return jsonify({'success': False, 'error': 'No valid fields to update'}), 400
        
        # Update project
        project = update_project_metadata(current_user.id, project_id, **update_data)
        
        return jsonify({
            'success': True,
            'message': 'Project updated successfully',
            'project': project.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"Update project error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while updating the project'}), 500


@project_bp.route('/<int:project_id>/access', methods=['POST'])
@token_required
def update_project_access(current_user, project_id):
    """Update project last accessed time"""
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, 
            user_id=current_user.id,
            is_active=True
        ).first()
        
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        project.update_last_accessed()
        
        return jsonify({
            'success': True,
            'message': 'Project access updated',
            'project': project.to_dict()
        }), 200
        
    except Exception as e:
        print(f"Update project access error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while updating project access'}), 500


@project_bp.route('/<int:project_id>/deactivate', methods=['POST'])
@token_required
def deactivate_project(current_user, project_id):
    """Deactivate a project (soft delete)"""
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, 
            user_id=current_user.id,
            is_active=True
        ).first()
        
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        project.deactivate()
        
        return jsonify({
            'success': True,
            'message': 'Project deactivated successfully',
            'project': project.to_dict()
        }), 200
        
    except Exception as e:
        print(f"Deactivate project error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while deactivating the project'}), 500


@project_bp.route('/by-name/<project_name>', methods=['GET'])
@token_required
def get_project_by_name(current_user, project_name):
    """Get a project by name"""
    try:
        project = ProjectMetadata.get_project_by_name(current_user.id, project_name)
        
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        return jsonify({
            'success': True,
            'project': project.to_dict(include_path=True)
        }), 200
        
    except Exception as e:
        print(f"Get project by name error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while retrieving the project'}), 500


@project_bp.route('/types', methods=['GET'])
@token_required
def get_project_types(current_user):
    """Get available project types for the user"""
    try:
        # Get unique project types for the user
        project_types = db.session.query(ProjectMetadata.project_type)\
                                  .filter_by(user_id=current_user.id, is_active=True)\
                                  .distinct().all()
        
        types_list = [pt[0] for pt in project_types if pt[0]]
        
        # Get unique languages
        languages = db.session.query(ProjectMetadata.language)\
                              .filter_by(user_id=current_user.id, is_active=True)\
                              .distinct().all()
        
        languages_list = [lang[0] for lang in languages if lang[0]]
        
        # Get unique frameworks
        frameworks = db.session.query(ProjectMetadata.framework)\
                               .filter_by(user_id=current_user.id, is_active=True)\
                               .distinct().all()
        
        frameworks_list = [fw[0] for fw in frameworks if fw[0]]
        
        return jsonify({
            'success': True,
            'project_types': types_list,
            'languages': languages_list,
            'frameworks': frameworks_list
        }), 200
        
    except Exception as e:
        print(f"Get project types error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while retrieving project types'}), 500