const api = require('../../utils/request')
const { formatNumber, formatHeat } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    darkMode: false,
    dramaA: null,
    dramaB: null,
    compareData: null,
    compareTab: 'heat',
    loading: false,
    _selectSlot: ''
  },

  onLoad(options) {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })

    // 如果带了id参数，预填充
    if (options.id) {
      this.loadDramaInfo(options.id, 'A')
    }
  },

  // 选择剧集 — 以 pick 模式打开搜索页，搜索页通过 eventChannel 回传选中项
  selectDrama(e) {
    const slot = e.currentTarget.dataset.slot
    this.data._selectSlot = slot

    wx.navigateTo({
      url: '/pages/search/search?pick=1',
      events: {
        selectDrama: (drama) => {
          this.onDramaSelected(drama, slot)
        }
      }
    })
  },

  onDramaSelected(drama, slot) {
    if (slot === 'A') {
      this.setData({ dramaA: drama })
    } else {
      this.setData({ dramaB: drama })
    }

    // 两个都有时，加载对比数据
    if (this.data.dramaA && this.data.dramaB) {
      this.loadCompareData()
    }
  },

  removeDrama(e) {
    const slot = e.currentTarget.dataset.slot
    if (slot === 'A') {
      this.setData({ dramaA: null, compareData: null })
    } else {
      this.setData({ dramaB: null, compareData: null })
    }
  },

  async loadDramaInfo(id, slot) {
    try {
      const data = await api.get(`/drama/${id}`)
      if (slot === 'A') {
        this.setData({ dramaA: data })
      } else {
        this.setData({ dramaB: data })
      }
    } catch (e) {
      console.error('加载剧集信息失败', e)
    }
  },

  async loadCompareData() {
    this.setData({ loading: true })
    try {
      const data = await api.get('/heat/realtime/compare', {
        drama_ids: this.data.dramaA.id + ',' + this.data.dramaB.id,
        tab: this.data.compareTab
      })

      // 格式化对比指标
      const metrics = (data.metrics || []).map(m => ({
        ...m,
        value_a: this._formatMetricValue(m.raw_a, m.type),
        value_b: this._formatMetricValue(m.raw_b, m.type),
        a_win: Number(m.raw_a) > Number(m.raw_b),
        b_win: Number(m.raw_b) > Number(m.raw_a)
      }))

      const scoreA = Number(data.score_a)
      const scoreB = Number(data.score_b)
      const hasScore = Number.isFinite(scoreA) && Number.isFinite(scoreB) && (scoreA + scoreB) > 0
      const aPct = hasScore ? Math.round(scoreA / (scoreA + scoreB) * 100) : 50
      const bPct = 100 - aPct

      this.setData({
        compareData: {
          metrics,
          a_score_pct: aPct,
          b_score_pct: bPct,
          summary: data.summary || '两部剧各有千秋'
        },
        loading: false
      })
    } catch (e) {
      console.error('加载对比数据失败', e)
      this.setData({ loading: false })
      wx.showToast({ title: '对比数据加载失败', icon: 'none' })
    }
  },

  _formatMetricValue(val, type) {
    if (!val && val !== 0) return '-'
    if (type === 'number') return formatNumber(val)
    if (type === 'heat') return formatHeat(val)
    if (type === 'score') return Number(val).toFixed(1)
    return String(val)
  },

  switchCompareTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ compareTab: tab })
    if (this.data.dramaA && this.data.dramaB) {
      this.loadCompareData()
    }
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 剧集对比',
      path: '/pages/compare/compare'
    }
  }
})
