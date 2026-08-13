// CanonWriter API 客户端
// 与 api_server.py (FastAPI) 通信
// 自动识别环境：本地用 localhost，线上用部署地址
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://canonwriter-api.onrender.com'; // TODO: 部署后端后替换为实际地址

const API = {
  // 健康检查
  async health() {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) throw new Error('后端连接失败');
    return res.json();
  },

  // 上传文件 (Lore库)
  async uploadFiles(fileList) {
    const fd = new FormData();
    for (const file of fileList) {
      fd.append('files', file);
    }
    const res = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      body: fd,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '上传失败');
    }
    return res.json();
  },

  // 获取已上传文件信息
  async getLoreFiles() {
    const res = await fetch(`${API_BASE}/api/lore/files`);
    if (!res.ok) throw new Error('获取文件列表失败');
    return res.json();
  },

  // 删除已上传文件
  async deleteLoreFile(fileId) {
    const res = await fetch(`${API_BASE}/api/lore/files/${fileId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('删除文件失败');
    return res.json();
  },

  // 重建角色提取
  async rebuildCharacters() {
    const res = await fetch(`${API_BASE}/api/lore/rebuild`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '重建失败');
    }
    return res.json();
  },

  // 获取情绪轨迹列表
  async getTrajectories() {
    const res = await fetch(`${API_BASE}/api/emotion/trajectories`);
    if (!res.ok) throw new Error('获取轨迹失败');
    return res.json();
  },

  // 生成情感规划
  async planEmotion(trajectory, character, userRequest) {
    const res = await fetch(`${API_BASE}/api/emotion/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trajectory, character, user_request: userRequest }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '规划失败');
    }
    return res.json();
  },

  // 获取角色列表
  async getCharacters() {
    const res = await fetch(`${API_BASE}/api/characters`);
    if (!res.ok) throw new Error('获取角色失败');
    return res.json();
  },

  // 获取单角色时间线
  async getTimeline(character) {
    const res = await fetch(`${API_BASE}/api/timeline/${encodeURIComponent(character)}`);
    if (!res.ok) throw new Error('获取时间线失败');
    return res.json();
  },

  // 生成正文
  async generate(query, mode = 'create') {
    const res = await fetch(`${API_BASE}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, mode }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '生成失败');
    }
    return res.json();
  },

  // 修改正文
  async revise(original, instruction, query = '') {
    const res = await fetch(`${API_BASE}/api/revise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ original, instruction, query }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '修改失败');
    }
    return res.json();
  },
};
