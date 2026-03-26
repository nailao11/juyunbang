const api = require('../../utils/request')
const { formatNumber, formatHeat, formatChange } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    dramaId: '',
    drama: {},
    heatData: {},
    powerData: {
      total: 0,
      dimensions: []
    },
    playData: {},
    socialData: [],
    relatedList: [],
    trackingStatus: '',
    showFullSynopsis: false,
    scrolled: false,
    darkMode: false,
    statusBarHeight: 20
  },

  onLoad(options) {
    const systemInfo = app.globalData.systemInfo || wx.getSystemInfoSync()
    this.setData({
      dramaId: options.id || '',
      statusBarHeight: systemInfo.statusBarHeight || 20,
      darkMode: app.globalData.themeMode === 'dark'
    })

    if (options.id) {
      this.loadDramaDetail(options.id)
      this.loadRelated(options.id)
      this.loadTrackingStatus(options.id)
    }
  },

  onShow() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  onPageScroll(e) {
    this.setData({ scrolled: e.scrollTop > 200 })
  },

  // 加载剧集详情（包含热度、指数、播放量、社交数据）
  async loadDramaDetail(id) {
    try {
      const data = await api.get(`/drama/${id}`)
      // 计算星星数
      data.star_count = data.douban_score ? Math.round(data.douban_score / 2) : 0
      // 处理类型标签
      if (data.genre && typeof data.genre === 'string') {
        data.genres = data.genre.split(/[,，/]/).map(s => s.trim()).filter(Boolean)
      } else {
        data.genres = data.genres || []
      }
      this.setData({ drama: data })

      // 更新标题
      wx.setNavigationBarTitle({ title: data.title || '剧集详情' })

      // 从详情接口返回的数据中提取热度数据
      this._processHeatData(data.current_heat)
      // 提取剧力指数
      this._processPowerData(data.drama_index)
      // 提取播放量数据
      this._processPlayData(data.play_data)
      // 提取社交媒体数据
      this._processSocialData(data.social_data)
    } catch (e) {
      console.error('加载剧集详情失败', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  // 处理热度数据
  _processHeatData(heatList) {
    if (!heatList || heatList.length === 0) {
      this.setData({ heatData: {} })
      return
    }
    // 取最高热度平台的数据
    const top = heatList[0]
    this.setData({
      heatData: {
        current: formatHeat(top.heat_value),
        today_peak: formatHeat(top.heat_value),
        rank: top.heat_rank || '-',
        trend: 'flat',
        change_display: '-',
        platforms: heatList.map(h => ({
          name: h.platform_name || h.name,
          value: formatHeat(h.heat_value),
          color: h.color || '#667eea'
        }))
      }
    })
  },

  // 处理剧力指数数据
  _processPowerData(indexData) {
    if (!indexData) {
      this.setData({ powerData: { total: 0, dimensions: [] } })
      return
    }
    this.setData({
      powerData: {
        total: indexData.index_total || 0,
        dimensions: [
          { name: '热度', value: indexData.index_heat || 0 },
          { name: '口碑', value: indexData.index_reputation || 0 },
          { name: '播放', value: indexData.index_playcount || 0 },
          { name: '讨论', value: indexData.index_social || 0 }
        ]
      }
    })
  },

  // 处理播放量数据
  _processPlayData(playData) {
    if (!playData) {
      this.setData({ playData: {} })
      return
    }
    this.setData({
      playData: {
        total_display: formatNumber(playData.total_play),
        today_display: formatNumber(playData.latest_daily_play),
        avg_display: formatNumber(playData.avg_episode_play),
        change_pct: '-',
        trend: 'flat'
      }
    })
  },

  // 处理社交媒体数据
  _processSocialData(socialData) {
    if (!socialData) {
      this.setData({
        socialData: [
          { platform: '微博', icon: '微', color: '#E6162D', metric: '话题阅读', value_display: '-', trend: 'flat', change_display: '-' },
          { platform: '抖音', icon: '抖', color: '#000000', metric: '相关播放', value_display: '-', trend: 'flat', change_display: '-' },
          { platform: '百度', icon: '百', color: '#2932E1', metric: '搜索指数', value_display: '-', trend: 'flat', change_display: '-' }
        ]
      })
      return
    }
    this.setData({
      socialData: [
        {
          platform: '微博', icon: '微', color: '#E6162D',
          metric: '话题阅读',
          value_display: formatNumber(socialData.weibo_topic_read_incr),
          trend: 'flat', change_display: '-'
        },
        {
          platform: '抖音', icon: '抖', color: '#000000',
          metric: '相关播放',
          value_display: formatNumber(socialData.douyin_topic_views_incr),
          trend: 'flat', change_display: '-'
        },
        {
          platform: '百度', icon: '百', color: '#2932E1',
          metric: '搜索指数',
          value_display: formatNumber(socialData.baidu_index),
          trend: 'flat', change_display: '-'
        }
      ]
    })
  },

  // 加载相关推荐
  async loadRelated(id) {
    try {
      const data = await api.get(`/drama/${id}/related`, { limit: 8 })
      this.setData({ relatedList: data.list || data || [] })
    } catch (e) {
      console.error('加载相关推荐失败', e)
    }
  },

  // 加载追剧状态
  async loadTrackingStatus(id) {
    try {
      const data = await api.get(`/tracking/status/${id}`, {}, true)
      this.setData({ trackingStatus: data.status || '' })
    } catch (e) {
      // 未登录或未追
    }
  },

  // 追剧/想看
  async toggleTracking(e) {
    const status = e.currentTarget.dataset.status
    const current = this.data.trackingStatus

    try {
      if (current === status) {
        // 取消
        await api.del(`/tracking/${this.data.dramaId}`)
        this.setData({ trackingStatus: '' })
        wx.showToast({ title: '已取消', icon: 'success' })
      } else {
        // 添加/更新
        await api.post('/tracking/add', {
          drama_id: this.data.dramaId,
          status: status
        })
        this.setData({ trackingStatus: status })
        const label = status === 'watching' ? '已加入追剧' : '已加入想看'
        wx.showToast({ title: label, icon: 'success' })
      }
    } catch (e) {
      wx.showToast({ title: '请先登录', icon: 'none' })
    }
  },

  // 展开/收起简介
  toggleSynopsis() {
    this.setData({ showFullSynopsis: !this.data.showFullSynopsis })
  },

  // 去写笔记
  goNotes() {
    wx.navigateTo({
      url: `/pages/notes/notes?drama_id=${this.data.dramaId}&title=${this.data.drama.title || ''}`
    })
  },

  // 返回
  goBack() {
    wx.navigateBack({ delta: 1 })
  },

  // 跳转详情（相关推荐）
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.redirectTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  // 分享 — 触发微信原生分享菜单
  onShareTap() {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ['shareAppMessage', 'shareTimeline']
    })
  },

  onShareAppMessage() {
    return {
      title: `${this.data.drama.title || '剧集详情'} - 剧云榜`,
      path: `/pages/drama-detail/drama-detail?id=${this.data.dramaId}`
    }
  }
})
