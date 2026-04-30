"""Project metadata routes for managing project information"""
from flask import Blueprint, request, jsonify
from server.models import ProjectMetadata
from server.middleware.database import db
from server.utils.auth_utils import token_required
from server.utils.db_utils import create_project_metadata, update_project_metadata
from server.utils.validators import sanitize_input
from server.utils.context_builder import build_project_context, invalidate_cache
from server.utils.structured_logger import get_structured_logger
from server.utils.monitoring import capture_exception

project_bp = Blueprint('project', __name__, url_prefix='/api/projects')
logger = get_structured_logger()


# ── Existing routes (unchanged) ───────────────────────────────────────────────

@project_bp.route('/', methods=['POST'])
@token_required
def create_project(current_user):
    """Create a new project"""
    try:
        data = request.get_json()
        if not data:
            logger.warning(
                "No data provided for project creation",
                event_type='project_operation',
                operation='create_project',
                user_id=current_user.id,
                reason='no_data'
            )
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        project_name = data.get('project_name')
        if not project_name:
            logger.warning(
                "Project name required for project creation",
                event_type='project_operation',
                operation='create_project',
                user_id=current_user.id,
                reason='missing_project_name'
            )
            return jsonify({'success': False, 'error': 'Project name is required'}), 400

        project_name = sanitize_input(project_name, 255)
        description = sanitize_input(data.get('description', ''), 1000) or None
        project_type = sanitize_input(data.get('project_type', ''), 50) or None
        language = sanitize_input(data.get('language', ''), 50) or None
        framework = sanitize_input(data.get('framework', ''), 100) or None
        project_path = sanitize_input(data.get('project_path', ''), 500) or None

        project = create_project_metadata(
            user_id=current_user.id,
            project_name=project_name,
            description=description,
            project_type=project_type,
            language=language,
            framework=framework,
            project_path=project_path,
        )

        logger.info(
            f"Project created successfully: {project_name}",
            event_type='project_operation',
            operation='project_created',
            user_id=current_user.id,
            project_id=project.id,
            project_name=project_name,
            project_type=project_type,
            language=language,
            framework=framework
        )

        return jsonify({
            'success': True,
            'message': 'Project created successfully',
            'project': project.to_dict(),
        }), 201

    except ValueError as e:
        logger.warning(
            f"Validation error in project creation: {str(e)}",
            event_type='project_operation',
            operation='create_project',
            user_id=current_user.id,
            error_type='validation_error',
            error_message=str(e)
        )
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.log_error_with_context(
            e,
            {
                'event_type': 'project_operation',
                'operation': 'create_project',
                'user_id': current_user.id,
                'project_name': data.get('project_name') if data else None
            }
        )
        capture_exception(e, {'route': 'project.create_project', 'user_id': current_user.id})
        return jsonify({'success': False, 'error': 'An error occurred while creating the project'}), 500


@project_bp.route('/', methods=['GET'])
@project_bp.route('/list', methods=['GET'])
@token_required
def list_projects(current_user):
    """List all projects for the current user"""
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        project_type = request.args.get('project_type')
        language = request.args.get('language')

        query = ProjectMetadata.query.filter_by(user_id=current_user.id)
        if active_only:
            query = query.filter_by(is_active=True)
        if project_type:
            query = query.filter_by(project_type=project_type)
        if language:
            query = query.filter_by(language=language)

        projects = query.order_by(ProjectMetadata.updated_at.desc()).all()

        return jsonify({
            'success': True,
            'projects': [project.to_dict() for project in projects],
            'total_projects': len(projects),
            'filters': {
                'active_only': active_only,
                'project_type': project_type,
                'language': language,
            },
        }), 200

    except Exception as e:
        logger.exception("List projects error")
        capture_exception(e, {'route': 'project.list_projects', 'user_id': current_user.id})
        return jsonify({'success': False, 'error': 'An error occurred while retrieving projects'}), 500


@project_bp.route('/<int:project_id>', methods=['GET'])
@token_required
def get_project(current_user, project_id):
    """Get a specific project by ID"""
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        return jsonify({'success': True, 'project': project.to_dict(include_path=True)}), 200

    except Exception as e:
        logger.exception("Get project error")
        capture_exception(e, {'route': 'project.get_project', 'user_id': current_user.id, 'project_id': project_id})
        return jsonify({'success': False, 'error': 'An error occurred while retrieving the project'}), 500


@project_bp.route('/<int:project_id>', methods=['PUT'])
@token_required
def update_project(current_user, project_id):
    """Update a project"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        update_data = {}
        field_limits = {
            'project_name': 255,
            'description': 1000,
            'project_type': 50,
            'language': 50,
            'framework': 100,
            'project_path': 500,
        }
        for field, limit in field_limits.items():
            if field in data:
                update_data[field] = sanitize_input(data[field], limit) or None

        if not update_data:
            return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

        project = update_project_metadata(current_user.id, project_id, **update_data)

        # Invalidate context cache for this project if path is changing
        if 'project_path' in update_data and update_data['project_path']:
            invalidate_cache(update_data['project_path'])

        return jsonify({
            'success': True,
            'message': 'Project updated successfully',
            'project': project.to_dict(),
        }), 200

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.exception("Update project error")
        capture_exception(e, {'route': 'project.update_project', 'user_id': current_user.id, 'project_id': project_id})
        return jsonify({'success': False, 'error': 'An error occurred while updating the project'}), 500


@project_bp.route('/<int:project_id>/access', methods=['POST'])
@token_required
def update_project_access(current_user, project_id):
    """Update project last accessed time"""
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        project.update_last_accessed()
        return jsonify({'success': True, 'message': 'Project access updated', 'project': project.to_dict()}), 200

    except Exception as e:
        logger.exception("Update project access error")
        capture_exception(e, {'route': 'project.update_project_access', 'user_id': current_user.id, 'project_id': project_id})
        return jsonify({'success': False, 'error': 'An error occurred while updating project access'}), 500


@project_bp.route('/<int:project_id>/deactivate', methods=['POST'])
@token_required
def deactivate_project(current_user, project_id):
    """Deactivate a project (soft delete)"""
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        project.deactivate()
        return jsonify({'success': True, 'message': 'Project deactivated successfully', 'project': project.to_dict()}), 200

    except Exception as e:
        logger.exception("Deactivate project error")
        capture_exception(e, {'route': 'project.deactivate_project', 'user_id': current_user.id, 'project_id': project_id})
        return jsonify({'success': False, 'error': 'An error occurred while deactivating the project'}), 500


@project_bp.route('/by-name/<project_name>', methods=['GET'])
@token_required
def get_project_by_name(current_user, project_name):
    """Get a project by name"""
    try:
        project = ProjectMetadata.get_project_by_name(current_user.id, project_name)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        return jsonify({'success': True, 'project': project.to_dict(include_path=True)}), 200

    except Exception as e:
        logger.exception("Get project by name error")
        capture_exception(e, {'route': 'project.get_project_by_name', 'user_id': current_user.id})
        return jsonify({'success': False, 'error': 'An error occurred while retrieving the project'}), 500


@project_bp.route('/types', methods=['GET'])
@token_required
def get_project_types(current_user):
    """Get available project types for the user"""
    try:
        project_types = db.session.query(ProjectMetadata.project_type)\
            .filter_by(user_id=current_user.id, is_active=True).distinct().all()
        languages = db.session.query(ProjectMetadata.language)\
            .filter_by(user_id=current_user.id, is_active=True).distinct().all()
        frameworks = db.session.query(ProjectMetadata.framework)\
            .filter_by(user_id=current_user.id, is_active=True).distinct().all()

        return jsonify({
            'success': True,
            'project_types': [pt[0] for pt in project_types if pt[0]],
            'languages': [lang[0] for lang in languages if lang[0]],
            'frameworks': [fw[0] for fw in frameworks if fw[0]],
        }), 200

    except Exception as e:
        logger.exception("Get project types error")
        capture_exception(e, {'route': 'project.get_project_types', 'user_id': current_user.id})
        return jsonify({'success': False, 'error': 'An error occurred while retrieving project types'}), 500


# ── NEW: Context endpoint ─────────────────────────────────────────────────────

@project_bp.route('/<int:project_id>/context', methods=['POST'])
@token_required
def get_project_context(current_user, project_id):
    """
    Pre-fetch and return project context for the frontend.

    The IDE calls this whenever the active file changes so it can attach the
    serialised context_payload to subsequent agent requests without waiting
    for the agent to do its own file exploration.

    Expected JSON body:
    {
        "current_file_path": "/abs/path/to/file.rs",   // required
        "recently_modified": ["/path/a.rs", "/path/b.rs"],  // optional
        "force_refresh": false                           // optional
    }

    Returns:
    {
        "success": true,
        "context_payload": { ... },   // pass this verbatim to the agent
        "summary": {
            "current_file": "src/lib.rs",
            "related_files": ["src/contract.rs"],
            "total_chars": 4321,
            "cache_hit": false
        }
    }
    """
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if not project.project_path:
            return jsonify({'success': False, 'error': 'Project has no path configured'}), 400

        data = request.get_json() or {}
        current_file_path = data.get('current_file_path')
        recently_modified = data.get('recently_modified', [])
        force_refresh = bool(data.get('force_refresh', False))

        # Validate current_file_path is within the project to prevent path traversal
        if current_file_path:
            import os
            abs_project = os.path.realpath(project.project_path)
            abs_file = os.path.realpath(current_file_path)
            if not abs_file.startswith(abs_project):
                return jsonify({'success': False, 'error': 'File path is outside project directory'}), 400

        project_metadata = {
            'project_name': project.project_name,
            'project_type': project.project_type or '',
            'language': project.language or '',
            'framework': project.framework or '',
        }

        ctx = build_project_context(
            project_path=project.project_path,
            current_file_path=current_file_path,
            project_metadata=project_metadata,
            recently_modified=recently_modified,
            force_refresh=force_refresh,
        )

        # Build the payload the frontend will forward to the agent
        context_payload = {
            'project_path': project.project_path,
            'current_file_path': current_file_path,
            'project_metadata': project_metadata,
            'recently_modified': recently_modified,
        }

        summary = {
            'current_file': (
                _relative_path(ctx.current_file.path, project.project_path)
                if ctx.current_file else None
            ),
            'related_files': [
                _relative_path(rf.path, project.project_path)
                for rf in ctx.related_files
            ],
            'total_chars': ctx.total_chars,
            'cache_hit': ctx.cache_hit,
            'project_type': ctx.project_type,
            'language': ctx.language,
        }

        return jsonify({
            'success': True,
            'context_payload': context_payload,
            'summary': summary,
        }), 200

    except Exception as e:
        logger.exception("Get project context error")
        capture_exception(e, {
            'route': 'project.get_project_context',
            'user_id': current_user.id,
            'project_id': project_id,
        })
        return jsonify({'success': False, 'error': 'An error occurred while building project context'}), 500


@project_bp.route('/<int:project_id>/context/invalidate', methods=['POST'])
@token_required
def invalidate_project_context(current_user, project_id):
    """
    Invalidate the context cache for a project.

    Call this from the frontend whenever a file is saved or created so the
    next context fetch picks up the changes.
    """
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.project_path:
            invalidate_cache(project.project_path)

        return jsonify({'success': True, 'message': 'Context cache invalidated'}), 200

    except Exception as e:
        logger.exception("Invalidate context error")
        capture_exception(e, {
            'route': 'project.invalidate_project_context',
            'user_id': current_user.id,
            'project_id': project_id,
        })
        return jsonify({'success': False, 'error': 'An error occurred while invalidating context'}), 500


@project_bp.route('/<int:project_id>/files/save', methods=['POST'])
@token_required
def save_project_file(current_user, project_id):
    """
    Save file content to the filesystem.
    
    Expected JSON body:
    {
        "file_path": "/absolute/path/to/file.rs",
        "content": "..."
    }
    """
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if not project.project_path:
            return jsonify({'success': False, 'error': 'Project has no path configured'}), 400

        data = request.get_json() or {}
        file_path = data.get('file_path')
        content = data.get('content')

        if not file_path:
            return jsonify({'success': False, 'error': 'file_path is required'}), 400

        if content is None:
            return jsonify({'success': False, 'error': 'content is required'}), 400

        import os
        abs_project = os.path.realpath(project.project_path)
        abs_file = os.path.realpath(file_path)
        if not abs_file.startswith(abs_project):
            return jsonify({'success': False, 'error': 'File path is outside project directory'}), 400

        # Ensure directory exists
        os.makedirs(os.path.dirname(abs_file), exist_ok=True)

        with open(abs_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # Update last accessed time
        project.update_last_accessed()
        # Invalidate cache since the file changed
        from server.utils.context_builder import invalidate_cache
        invalidate_cache(project.project_path)

        return jsonify({
            'success': True, 
            'message': 'File saved successfully'
        }), 200

    except Exception as e:
        logger.exception("Save project file error")
        capture_exception(e, {
            'route': 'project.save_project_file',
            'user_id': current_user.id,
            'project_id': project_id,
        })
        return jsonify({'success': False, 'error': 'An error occurred while saving the file'}), 500


@project_bp.route('/<int:project_id>/files/read', methods=['GET'])
@token_required
def read_project_file(current_user, project_id):
    """
    Read file content from the filesystem.
    Query parameter: file_path (e.g. ?file_path=/path/to/file.rs)
    """
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if not project.project_path:
            return jsonify({'success': False, 'error': 'Project has no path configured'}), 400

        file_path = request.args.get('file_path')
        if not file_path:
            return jsonify({'success': False, 'error': 'file_path query parameter is required'}), 400

        import os
        abs_project = os.path.realpath(project.project_path)
        abs_file = os.path.realpath(file_path)
        if not abs_file.startswith(abs_project):
            return jsonify({'success': False, 'error': 'File path is outside project directory'}), 400

        if not os.path.isfile(abs_file):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        with open(abs_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({
            'success': True,
            'content': content
        }), 200

    except Exception as e:
        logger.exception("Read project file error")
        capture_exception(e, {
            'route': 'project.read_project_file',
            'user_id': current_user.id,
            'project_id': project_id,
        })
        return jsonify({'success': False, 'error': 'An error occurred while reading the file'}), 500


@project_bp.route('/<int:project_id>/files/tree', methods=['GET'])
@token_required
def get_project_file_tree(current_user, project_id):
    """
    Get the file system tree structure for a project.
    Query parameter: path (optional, relative to project root)
    """
    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if not project.project_path:
            return jsonify({'success': False, 'error': 'Project has no path configured'}), 400

        import os
        from pathlib import Path

        # Get the requested path relative to project root
        rel_path = request.args.get('path', '')
        if rel_path:
            # Security: ensure the relative path doesn't escape project root
            if '..' in rel_path or rel_path.startswith('/'):
                return jsonify({'success': False, 'error': 'Invalid path'}), 400
            target_path = os.path.join(project.project_path, rel_path)
        else:
            target_path = project.project_path

        # Ensure the target path is within the project directory
        abs_project = os.path.realpath(project.project_path)
        abs_target = os.path.realpath(target_path)
        if not abs_target.startswith(abs_project):
            return jsonify({'success': False, 'error': 'Path is outside project directory'}), 400

        if not os.path.exists(abs_target):
            return jsonify({'success': False, 'error': 'Path does not exist'}), 404

        def build_tree_node(path, name, is_dir, relative_to):
            """Build a tree node for a file or directory"""
            node = {
                'name': name,
                'path': os.path.relpath(path, relative_to) if path != relative_to else '',
                'type': 'directory' if is_dir else 'file',
                'children': [] if is_dir else None
            }
            
            if is_dir:
                try:
                    # Sort entries: directories first, then files, both alphabetically
                    entries = sorted(os.listdir(path), key=lambda x: (os.path.isfile(os.path.join(path, x)), x.lower()))
                    for entry in entries:
                        entry_path = os.path.join(path, entry)
                        entry_is_dir = os.path.isdir(entry_path)
                        
                        # Skip hidden files and directories
                        if entry.startswith('.'):
                            continue
                            
                        # Skip common ignore patterns
                        if entry in ['node_modules', '__pycache__', '.git', 'target', 'dist', 'build']:
                            continue
                            
                        child_node = build_tree_node(entry_path, entry, entry_is_dir, relative_to)
                        if child_node:
                            node['children'].append(child_node)
                except (OSError, PermissionError):
                    # Skip directories we can't read
                    pass
            
            return node

        # Build the tree starting from the target path
        tree_root = build_tree_node(abs_target, os.path.basename(abs_target) or '.', os.path.isdir(abs_target), abs_project)

        return jsonify({
            'success': True,
            'tree': tree_root,
            'project_path': project.project_path
        }), 200

    except Exception as e:
        logger.exception("Get project file tree error")
        capture_exception(e, {
            'route': 'project.get_project_file_tree',
            'user_id': current_user.id,
            'project_id': project_id,
        })
        return jsonify({'success': False, 'error': 'An error occurred while retrieving file tree'}), 500


# ── Helper ────────────────────────────────────────────────────────────────────

def _relative_path(absolute: str, base: str) -> str:
    import os
    try:
        return os.path.relpath(absolute, base)
    except ValueError:
        return absolute