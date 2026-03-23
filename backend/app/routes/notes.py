from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..utils.db import query, query_one, insert, execute
from ..utils.response import success, error

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/<int:drama_id>', methods=['GET'])
@jwt_required()
def get_notes(drama_id):
    """获取某剧的笔记列表"""
    user_id = get_jwt_identity()

    notes = query(
        "SELECT id, episode_number, content, is_private, created_at, updated_at "
        "FROM user_notes "
        "WHERE user_id = %s AND drama_id = %s "
        "ORDER BY episode_number ASC, created_at DESC",
        (user_id, drama_id)
    )
    return success(notes)


@notes_bp.route('', methods=['POST'])
@jwt_required()
def create_note():
    """创建笔记"""
    user_id = get_jwt_identity()
    data = request.get_json()

    drama_id = data.get('drama_id')
    content = data.get('content', '').strip()
    episode_number = data.get('episode_number')
    is_private = data.get('is_private', 1)

    if not drama_id or not content:
        return error('缺少必要参数', 400)

    note_id = insert(
        "INSERT INTO user_notes (user_id, drama_id, episode_number, content, is_private) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, drama_id, episode_number, content, is_private)
    )

    return success({'note_id': note_id}, message='笔记创建成功')


@notes_bp.route('/<int:note_id>', methods=['PUT'])
@jwt_required()
def update_note(note_id):
    """编辑笔记"""
    user_id = get_jwt_identity()
    data = request.get_json()

    content = data.get('content', '').strip()
    if not content:
        return error('笔记内容不能为空', 400)

    affected = execute(
        "UPDATE user_notes SET content = %s, updated_at = NOW() "
        "WHERE id = %s AND user_id = %s",
        (content, note_id, user_id)
    )

    if affected == 0:
        return error('笔记不存在', 404)

    return success(message='笔记更新成功')


@notes_bp.route('/<int:note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    """删除笔记"""
    user_id = get_jwt_identity()

    affected = execute(
        "DELETE FROM user_notes WHERE id = %s AND user_id = %s",
        (note_id, user_id)
    )

    if affected == 0:
        return error('笔记不存在', 404)

    return success(message='笔记已删除')
