const api = require('../../utils/request')
const { formatNumber, formatHeat, formatChange, formatFullDate, getWeekDay } = require('../../utils/format')

const app = getApp()

const TAB_MAP = {
  play: { api: '/daily/play-rank', label: '播放量' },
  heat: { api: '/daily/heat-rank', label: '热度' },
  power: { api: '/daily/index-rank', label: '剧力指数' },
  discuss: { api: '/daily/social-rank', label: '讨论度' }
}

const TAB_INDEX = { play: 0, heat: 1, power: 2, discuss: 3 }

Page({
  data: {
    mainTab: 'play',
    mainTabIndex: 0,
    periodTab: 'daily',
    typeFilter: '',
    currentDate: '',
    displayDate: '',
    weekday: '',
    isToday: true,
    rankList: [],
    loading: true,
    darkMode: false,
    page: 1,
    hasMore: true
  },

  onLoad() {
    const today = this._getToday()
    this.setData({
      currentDate: today,
      displayDate: today,
      weekday: getWeekDay(today),
      isToday: true
    })
    this.loadRankData()
  },

  onShow() {
    const darkMode = app.globalData.themeMode === 'dark'
    this.setData({ darkMode })
    const bgColor = darkMode ? '#171923' : '#f4f5f7'
    wx.setBackgroundColor({
      backgroundColor: bgColor,
      backgroundColorTop: bgColor,
      backgroundColorBottom: bgColor
    })
    wx.setNavigationBarColor({
      frontColor: darkMode ? '#ffffff' : '#000000',
      backgroundColor: bgColor,
      animation: { duration: 0 }
    })
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    this.loadRankData().then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.setData({ page: this.data.page + 1 })
      this.loadRankData(true)
    }
  },

  // 加载排行数据
  async loadRankData(append = false) {
    if (!append) this.setData({ loading: true })

    try {
      const { mainTab, periodTab, typeFilter, currentDate, page } = this.data
      const config = TAB_MAP[mainTab]

      const params = {
        date: currentDate,
        period: periodTab,
        type: typeFilter,
        page,
        limit: 30
      }

      const data = await api.get(config.api, params)
      let list = data.list || data || []

      const maxVal = list.length > 0
        ? Math.max(...list.map(i => Number(i.value || i.play_count || i.heat_value || 0)))
        : 1

      list = list.map((item, idx) => ({
        ...item,
        value_display: this._formatValue(item, mainTab),
        change_display: item.change_pct ? formatChange(item.change_pct) : '',
        trend: item.trend || 'flat',
        bar_width: Math.round((Number(item.value || item.play_count || item.heat_value || 0) / maxVal) * 100),
        is_new: item.is_new || false,
        rank_change: item.rank_change
      }))

      const newList = append ? [...this.data.rankList, ...list] : list

      this.setData({
        rankList: newList,
        loading: false,
        hasMore: list.length >= 30
      })
    } catch (e) {
      console.error('加载排行数据失败', e)
      this.setData({ loading: false })
      if (!append) {
        wx.showToast({ title: '加载失败', icon: 'none' })
      }
    }
  },

  _formatValue(item, tab) {
    const val = item.value || item.play_count || item.heat_value || 0
    if (tab === 'play') return formatNumber(val)
    if (tab === 'heat') return formatHeat(val)
    if (tab === 'power') return val.toFixed ? val.toFixed(1) : val
    if (tab === 'discuss') return formatNumber(val)
    return formatNumber(val)
  },

  // 切换主Tab
  switchMainTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({
      mainTab: tab,
      mainTabIndex: TAB_INDEX[tab],
      page: 1,
      rankList: []
    })
    this.loadRankData()
  },

  // 切换时间维度
  switchPeriod(e) {
    const period = e.currentTarget.dataset.period
    this.setData({ periodTab: period, page: 1, rankList: [] })
    this.loadRankData()
  },

  // 切换类型筛选
  switchTypeFilter(e) {
    const type = e.currentTarget.dataset.type
    this.setData({ typeFilter: type, page: 1, rankList: [] })
    this.loadRankData()
  },

  // 前一天
  prevDay() {
    const d = new Date(this.data.currentDate)
    d.setDate(d.getDate() - 1)
    const dateStr = formatFullDate(d)
    this.setData({
      currentDate: dateStr,
      displayDate: dateStr,
      weekday: getWeekDay(dateStr),
      isToday: dateStr === this._getToday(),
      page: 1,
      rankList: []
    })
    this.loadRankData()
  },

  // 后一天
  nextDay() {
    if (this.data.isToday) return
    const d = new Date(this.data.currentDate)
    d.setDate(d.getDate() + 1)
    const dateStr = formatFullDate(d)
    this.setData({
      currentDate: dateStr,
      displayDate: dateStr,
      weekday: getWeekDay(dateStr),
      isToday: dateStr === this._getToday(),
      page: 1,
      rankList: []
    })
    this.loadRankData()
  },

  // 打开日期选择器
  openDatePicker() {
    const today = this._getToday()
    wx.showModal({
      title: '选择日期',
      editable: true,
      placeholderText: '格式：2026-03-25',
      success: (res) => {
        if (res.confirm && res.content) {
          const dateStr = res.content.trim()
          if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr) && dateStr <= today) {
            const parts = dateStr.split('-')
            const displayDate = `${parts[1]}月${parts[2]}日`
            const weekDay = ['周日','周一','周二','周三','周四','周五','周六'][new Date(dateStr).getDay()]
            this.setData({
              currentDate: dateStr,
              displayDate,
              weekday: weekDay,
              isToday: dateStr === today,
              page: 1,
              rankList: []
            })
            this.loadRankData()
          } else {
            wx.showToast({ title: '日期格式不正确或超过今天', icon: 'none' })
          }
        }
      }
    })
  },

  // 跳转详情
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  _getToday() {
    return formatFullDate(new Date())
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 数据中心',
      path: '/pages/datacenter/datacenter'
    }
  }
})
