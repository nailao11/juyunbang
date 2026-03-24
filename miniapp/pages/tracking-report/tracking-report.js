const api = require('../../utils/request')

const app = getApp()

Page({
  data: {
    darkMode: false,
    loading: true,
    reportPeriod: '',
    report: {
      total_dramas: 0,
      total_episodes: 0,
      total_hours: 0,
      total_notes: 0,
      genre_stats: [],
      timeline: [],
      rating_stats: []
    }
  },

  onLoad() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })

    // 设置报告期间
    const now = new Date()
    const year = now.getFullYear()
    const month = now.getMonth() + 1
    this.setData({ reportPeriod: `${year}年${month}月追剧报告` })

    this.loadReport()
  },

  async loadReport() {
    this.setData({ loading: true })
    try {
      const data = await api.get('/tracking/report/monthly', {}, true)

      // 处理类型偏好百分比
      if (data.genre_stats) {
        const maxCount = Math.max(...data.genre_stats.map(g => g.count), 1)
        data.genre_stats = data.genre_stats.map(g => ({
          ...g,
          percent: Math.round((g.count / maxCount) * 100)
        }))
      }

      // 处理评分分布百分比
      if (data.rating_stats) {
        const maxRating = Math.max(...data.rating_stats.map(r => r.count), 1)
        data.rating_stats = data.rating_stats.map(r => ({
          ...r,
          percent: Math.round((r.count / maxRating) * 100)
        }))
      }

      // 处理时间线日期
      if (data.timeline) {
        data.timeline = data.timeline.map(t => {
          const d = new Date(t.date)
          return {
            ...t,
            month: (d.getMonth() + 1) + '月',
            day: d.getDate() + '日'
          }
        })
      }

      this.setData({ report: data, loading: false })
    } catch (e) {
      console.error('加载追剧报告失败', e)
      this.setData({ loading: false })
      // 设置默认示例数据
      this.setData({
        report: {
          total_dramas: 0,
          total_episodes: 0,
          total_hours: 0,
          total_notes: 0,
          genre_stats: [],
          timeline: [],
          rating_stats: [
            { score: 5, count: 0, percent: 0 },
            { score: 4, count: 0, percent: 0 },
            { score: 3, count: 0, percent: 0 },
            { score: 2, count: 0, percent: 0 },
            { score: 1, count: 0, percent: 0 }
          ]
        }
      })
    }
  },

  onShareAppMessage() {
    return {
      title: `我的追剧报告 - ${this.data.reportPeriod}`,
      path: '/pages/tracking-report/tracking-report'
    }
  }
})
