const api = require('../../utils/request')
const { formatTimeAgo } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    darkMode: false,
    loading: true,
    isEditing: false,
    editingNoteId: null,
    notesList: [],
    currentDrama: null,
    noteContent: '',
    noteEpisode: '',
    noteImages: [],
    page: 1,
    hasMore: true
  },

  onLoad(options) {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })

    // 如果从剧集详情页进入，预填充剧集信息
    if (options.drama_id) {
      this.setData({
        isEditing: true,
        currentDrama: {
          id: options.drama_id,
          title: decodeURIComponent(options.title || ''),
          poster_url: options.poster || ''
        }
      })
    } else {
      this.loadNotes()
    }
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    this.loadNotes().then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading && !this.data.isEditing) {
      this.setData({ page: this.data.page + 1 })
      this.loadNotes(true)
    }
  },

  // 加载笔记列表
  async loadNotes(append = false) {
    if (!append) this.setData({ loading: true })

    try {
      const data = await api.get('/notes/list', {
        page: this.data.page,
        limit: 20
      }, true)

      let list = (data.list || data || []).map(note => ({
        ...note,
        time_display: formatTimeAgo(note.created_at || note.updated_at)
      }))

      const newList = append ? [...this.data.notesList, ...list] : list

      this.setData({
        notesList: newList,
        loading: false,
        hasMore: list.length >= 20
      })
    } catch (e) {
      console.error('加载笔记失败', e)
      this.setData({ loading: false })
    }
  },

  // 开始编辑
  startEdit() {
    this.setData({ isEditing: true })
  },

  // 取消编辑
  cancelEdit() {
    this.setData({
      isEditing: false,
      editingNoteId: null,
      currentDrama: null,
      noteContent: '',
      noteEpisode: '',
      noteImages: []
    })
  },

  // 编辑已有笔记
  editNote(e) {
    const note = e.currentTarget.dataset.note
    this.setData({
      isEditing: true,
      editingNoteId: note.id,
      currentDrama: note.drama_id ? {
        id: note.drama_id,
        title: note.drama_title,
        poster_url: note.poster_url
      } : null,
      noteContent: note.content || '',
      noteEpisode: note.episode || '',
      noteImages: note.images || []
    })
  },

  // 选择剧集
  selectDrama() {
    wx.navigateTo({
      url: '/pages/search/search',
      events: {
        selectDrama: (drama) => {
          this.setData({ currentDrama: drama })
        }
      }
    })
  },

  onNoteInput(e) {
    this.setData({ noteContent: e.detail.value })
  },

  onEpisodeInput(e) {
    this.setData({ noteEpisode: e.detail.value })
  },

  // 添加图片
  addNoteImage() {
    wx.chooseMedia({
      count: 9 - this.data.noteImages.length,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => {
        const paths = res.tempFiles.map(f => f.tempFilePath)
        this.setData({ noteImages: [...this.data.noteImages, ...paths] })
      }
    })
  },

  // 移除图片
  removeNoteImage(e) {
    const idx = e.currentTarget.dataset.index
    const images = [...this.data.noteImages]
    images.splice(idx, 1)
    this.setData({ noteImages: images })
  },

  // 保存笔记
  async saveNote() {
    const content = this.data.noteContent.trim()
    if (!content) {
      wx.showToast({ title: '请输入笔记内容', icon: 'none' })
      return
    }

    wx.showLoading({ title: '保存中...' })

    try {
      // 上传图片
      const imageUrls = []
      for (const path of this.data.noteImages) {
        if (path.startsWith('http')) {
          imageUrls.push(path)
          continue
        }
        try {
          const uploadRes = await new Promise((resolve, reject) => {
            wx.uploadFile({
              url: app.globalData.baseUrl + '/system/upload/image',
              filePath: path,
              name: 'file',
              header: { 'Authorization': 'Bearer ' + (app.globalData.token || '') },
              success: (res) => resolve(JSON.parse(res.data)),
              fail: reject
            })
          })
          if (uploadRes.data && uploadRes.data.url) {
            imageUrls.push(uploadRes.data.url)
          }
        } catch (e) {
          // 忽略上传失败
        }
      }

      const noteData = {
        content,
        drama_id: this.data.currentDrama ? this.data.currentDrama.id : '',
        episode: this.data.noteEpisode || '',
        images: imageUrls
      }

      if (this.data.editingNoteId) {
        await api.put(`/notes/${this.data.editingNoteId}`, noteData)
      } else {
        await api.post('/notes', noteData)
      }

      wx.hideLoading()
      wx.showToast({ title: '保存成功', icon: 'success' })

      this.cancelEdit()
      this.setData({ page: 1 })
      this.loadNotes()
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '保存失败', icon: 'none' })
    }
  },

  // 删除笔记
  deleteNote(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认删除',
      content: '删除后不可恢复，确定删除？',
      success: async (res) => {
        if (res.confirm) {
          try {
            await api.del(`/notes/${id}`)
            wx.showToast({ title: '已删除', icon: 'success' })
            this.setData({ page: 1 })
            this.loadNotes()
          } catch (e) {
            wx.showToast({ title: '删除失败', icon: 'none' })
          }
        }
      }
    })
  },

  // 预览图片
  previewImage(e) {
    const { urls, current } = e.currentTarget.dataset
    wx.previewImage({ current, urls })
  },

  // 跳转详情
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 追剧笔记',
      path: '/pages/notes/notes'
    }
  }
})
