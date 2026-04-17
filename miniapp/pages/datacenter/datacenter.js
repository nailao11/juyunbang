const api = require('../../utils/request')
const { formatNumber, formatHeat, formatChange, formatFullDate, getWeekDay } = require('../../utils/format')

const app = getApp()

// 主Tab元数据（用于下划线定位与默认展示）
const TAB_INDEX = { play: 0, heat: 1, power: 2, discuss: 3 }

// 各 (tab, period) 组合对应的后端接口、读值字段与格式化方式
// formatter: 'number' | 'heat' | 'score'
const ENDPOINT_MAP = {
  'play-daily':     { url: '/daily/play-rank',           valueField: 'total_daily_play', formatter: 'number' },
  'play-weekly':    { url: '/weekly/play-rank',          valueField: 'weekly_play',      formatter: 'number' },
  'play-monthly':   { url: '/weekly/monthly/play-rank',  valueField: 'monthly_play',     formatter: 'number' },

  'heat-daily':     { url: '/daily/heat-rank',           valueField: 'heat_avg',         formatter: 'heat' },
  'heat-weekly':    { url: '/weekly/heat-rank',          valueField: 'heat_avg',         formatter: 'heat' },
  'heat-monthly':   { url: '/weekly/monthly/heat-rank',  valueField: 'heat_avg',         formatter: 'heat' },

  'power-daily':    { url: '/daily/index-rank',          valueField: 'index_total',      formatter: 'score' },
  'power-weekly':   { url: '/weekly/index-rank',         valueField: 'avg_index',        formatter: 'score' },
  'power-monthly':  { url: '/weekly/monthly/index-rank', valueField: 'avg_index',        formatter: 'score' },

  'discuss-daily':  { url: '/daily/social-rank',         valueField: 'social_score',     formatter: 'number' },
  'discuss-weekly': { url: '/weekly/social-rank',        valueField: 'social_score',     formatter: 'number' },
  'discuss-monthly':{ url: '/weekly/monthly/social-rank',valueField: 'social_score',     formatter: 'number' }
}

// 将 YYYY-MM-DD 转为所在周的周一 YYYY-MM-DD
function getMondayOf(dateStr) {
  const d = new Date(dateStr)
  const day = d.getDay() // 0=周日, 1=周一, ..., 6=周六
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  return formatFullDate(d)
}

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

  // 构造给后端的日期参数（根据 period 选择 date/week_start/month）
  _buildDateParams() {
    const { periodTab, currentDate } = this.data
    if (periodTab === 'weekly') {
      return { week_start: getMondayOf(currentDate) }
    }
    if (periodTab === 'monthly') {
      return { month: currentDate.slice(0, 7) }
    }
    return { date: currentDate }
  },

  // 加载排行数据
  async loadRankData(append = false) {
    if (!append) this.setData({ loading: true })

    try {
      const { mainTab, periodTab, typeFilter, page } = this.data
      const key = `${mainTab}-${periodTab}`
      const config = ENDPOINT_MAP[key]

      if (!config) {
        console.error('未配置的组合', key)
        this.setData({ loading: false, rankList: [], hasMore: false })
        return
      }

      const params = {
        ...this._buildDateParams(),
        type: typeFilter,
        page,
        limit: 30
      }

      const data = await api.get(config.url, params)
      let list = data.list || data || []

      // 提取每项的数值，统一用于排序、格式化、进度条
      const getVal = (item) => {
        const v = item[config.valueField]
        return v !== null && v !== undefined ? Number(v) || 0 : 0
      }

      const maxVal = list.length > 0 ? Math.max(...list.map(getVal), 1) : 1

      list = list.map((item) => {
        const val = getVal(item)
        return {
          ...item,
          value_display: this._formatValue(val, config.formatter),
          change_display: item.change_pct ? formatChange(item.change_pct) : '',
          trend: item.trend || 'flat',
          bar_width: Math.max(0, Math.min(100, Math.round((val / maxVal) * 100))),
          is_new: item.is_new || false,
          rank_change: item.rank_change
        }
      })

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

  _formatValue(val, formatter) {
    if (val === null || val === undefined || isNaN(val)) return '-'
    if (formatter === 'heat') return formatHeat(val)
    if (formatter === 'score') return Number(val).toFixed(1)
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
      title: '热剧榜 — 数据中心',
      path: '/pages/datacenter/datacenter'
    }
  }
})
