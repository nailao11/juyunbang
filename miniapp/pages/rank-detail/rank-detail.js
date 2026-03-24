const api = require('../../utils/request')
const { formatNumber, formatHeat } = require('../../utils/format')

const app = getApp()

const RANK_CONFIG = {
  highscore: { title: '高分推荐', desc: '豆瓣高分剧集榜单', api: '/search/discover/high-rated' },
  'hidden-gem': { title: '冷门佳作', desc: '值得一看的宝藏剧集', api: '/search/discover/hidden-gems' },
  upcoming: { title: '待播期待榜', desc: '最受期待的待播剧集', api: '/search/discover/upcoming' },
  heat: { title: '热度总榜', desc: '全平台实时热度排行', api: '/daily/heat-rank' },
  play: { title: '播放量总榜', desc: '全平台累计播放排行', api: '/daily/play-rank' }
}

Page({
  data: {
    darkMode: false,
    loading: true,
    rankType: '',
    rankTitle: '',
    rankDesc: '',
    updateTime: '',
    rankList: [],
    page: 1,
    hasMore: true
  },

  onLoad(options) {
    const type = options.type || 'heat'
    const config = RANK_CONFIG[type] || RANK_CONFIG.heat

    this.setData({
      rankType: type,
      rankTitle: config.title,
      rankDesc: config.desc,
      darkMode: app.globalData.themeMode === 'dark'
    })

    wx.setNavigationBarTitle({ title: config.title })
    this.loadRankList()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    this.loadRankList().then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.setData({ page: this.data.page + 1 })
      this.loadRankList(true)
    }
  },

  async loadRankList(append = false) {
    if (!append) this.setData({ loading: true })

    const config = RANK_CONFIG[this.data.rankType] || RANK_CONFIG.heat

    try {
      const data = await api.get(config.api, {
        page: this.data.page,
        limit: 30
      })

      let list = (data.list || data || []).map(item => ({
        ...item,
        value_display: this._formatValue(item)
      }))

      const maxVal = list.length > 0
        ? Math.max(...list.map(i => Number(i.value || i.heat_value || i.play_count || 0)))
        : 1

      list = list.map(item => ({
        ...item,
        bar_width: Math.round((Number(item.value || item.heat_value || item.play_count || 0) / maxVal) * 100)
      }))

      const newList = append ? [...this.data.rankList, ...list] : list

      this.setData({
        rankList: newList,
        loading: false,
        hasMore: list.length >= 30,
        updateTime: data.update_time || ''
      })
    } catch (e) {
      console.error('加载榜单失败', e)
      this.setData({ loading: false })
    }
  },

  _formatValue(item) {
    const val = item.value || item.heat_value || item.play_count || item.douban_score || 0
    if (this.data.rankType === 'highscore' || this.data.rankType === 'hidden-gem') {
      return item.douban_score ? item.douban_score + '分' : '-'
    }
    if (this.data.rankType === 'upcoming') {
      return (item.expect_count || 0) + '人期待'
    }
    return formatNumber(val)
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  }
})
