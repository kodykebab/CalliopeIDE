"""Project metadata routes for managing project information"""
from flask import Blueprint, request, jsonify
from server.models import ProjectMetadata
from server.middleware.database import db
from server.utils.auth_utils import token_required
from server.utils.db_utils import create_project_metadata, update_project_metadata
from server.utils.validators import sanitize_input
from server.utils.context_builder import build_project_context, invalidate_cache
import logging
from server.utils.monitoring import capture_exception

project_bp = Blueprint('project', __name__, url_prefix='/api/projects')
logger = logging.getLogger(__name__)


# ── Existing routes (unchanged) ───────────────────────────────────────────────

@project_bp.route('/', methods=['POST'])
@token_required
def create_project(current_user):
    """Create a new project"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        project_name = data.get('project_name')
        if not project_name:
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

        return jsonify({
            'success': True,
            'message': 'Project created successfully',
            'project': project.to_dict(),
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.exception("Create project error")
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
    Return a recursive file-system tree for the project workspace.

    Query parameters:
        path  (optional) – subdirectory relative to project_path to list.
                           Defaults to the project root.

    Response:
    {
        "success": true,
        "tree": [
            {
                "name": "src",
                "path": "/abs/path/src",
                "relative_path": "src",
                "type": "directory",
                "children": [
                    {
                        "name": "lib.rs",
                        "path": "/abs/path/src/lib.rs",
                        "relative_path": "src/lib.rs",
                        "type": "file",
                        "extension": ".rs",
                        "size": 1024
                    }
                ]
            }
        ]
    }
    """
    import os

    # Directories / files to skip (common noise)
    IGNORED_NAMES = {
        '.git', '.svn', '__pycache__', 'node_modules', '.next',
        '.venv', 'venv', '.env', 'dist', 'build', '.pytest_cache',
        '.mypy_cache', '.tox', 'target', '.DS_Store', '.swc',
        'coverage', '.coverage', 'htmlcov', '.idea', '.vscode',
    }
    IGNORED_EXTENSIONS = {'.pyc', '.pyo', '.pyd', '.so', '.o', '.a'}
    MAX_DEPTH = 6   # prevent runaway recursion on large trees
    MAX_ENTRIES = 500  # safety cap on total nodes returned

    try:
        project = ProjectMetadata.query.filter_by(
            id=project_id, user_id=current_user.id, is_active=True
        ).first()

        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if not project.project_path:
            return jsonify({'success': False, 'error': 'Project has no path configured'}), 400

        abs_project = os.path.realpath(project.project_path)

        # Optional sub-path
        sub_path = request.args.get('path', '').strip().lstrip('/')
        if sub_path:
            target = os.path.realpath(os.path.join(abs_project, sub_path))
            if not target.startswith(abs_project):
                return jsonify({'success': False, 'error': 'Path is outside project directory'}), 400
        else:
            target = abs_project

        if not os.path.isdir(target):
            return jsonify({'success': False, 'error': 'Target path is not a directory'}), 400

        counter = {'n': 0}

        def build_tree(directory: str, depth: int) -> list:
            if depth > MAX_DEPTH or counter['n'] >= MAX_ENTRIES:
                return []

            entries = []
            try:
                items = sorted(os.scandir(directory), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return []

            for item in items:
                if item.name in IGNORED_NAMES:
                    continue
                _, ext = os.path.splitext(item.name)
                if ext in IGNORED_EXTENSIONS:
                    continue

                counter['n'] += 1
                if counter['n'] > MAX_ENTRIES:
                    break

                abs_item = os.path.realpath(item.path)
                rel = os.path.relpath(abs_item, abs_project)

                if item.is_dir(follow_symlinks=False):
                    children = build_tree(abs_item, depth + 1)
                    entries.append({
                        'name': item.name,
                        'path': abs_item,
                        'relative_path': rel,
                        'type': 'directory',
                        'children': children,
                    })
                else:
                    try:
                        size = item.stat().st_size
                    except OSError:
                        size = 0
                    entries.append({
                        'name': item.name,
                        'path': abs_item,
                        'relative_path': rel,
                        'type': 'file',
                        'extension': ext.lower(),
                        'size': size,
                    })

            return entries

        tree = build_tree(target, depth=0)

        return jsonify({
            'success': True,
            'project_path': abs_project,
            'tree': tree,
            'total_nodes': counter['n'],
        }), 200

    except Exception as e:
        logger.exception("Get project file tree error")
        capture_exception(e, {
            'route': 'project.get_project_file_tree',
            'user_id': current_user.id,
            'project_id': project_id,
        })
        return jsonify({'success': False, 'error': 'An error occurred while building the file tree'}), 500


# ── Helper ────────────────────────────────────────────────────────────────────

def _relative_path(absolute: str, base: str) -> str:
    import os
    try:
        return os.path.relpath(absolute, base)
    except ValueError:
        return absolute