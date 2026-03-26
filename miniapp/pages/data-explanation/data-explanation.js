const app = getApp()

Page({
  data: {
    darkMode: false,
    sections: [
      {
        icon: '🔥',
        title: '热度指标',
        items: [
          { name: '实时热度', desc: '综合各平台搜索指数、社交媒体讨论量、站内热度等多维数据，通过加权算法实时计算得出的热度值。每5分钟更新一次。' },
          { name: '热度趋势', desc: '与上一时间节点对比的热度变化百分比，上升/下降/持平，反映剧集热度的变化趋势。' },
          { name: '全平台排名', desc: '基于实时热度值在所有上线剧集中的排名位置。' }
        ]
      },
      {
        icon: '▶️',
        title: '播放量',
        items: [
          { name: '播放量数据', desc: '来自各视频平台公开的播放量数据，包含PC端、移动端、OTT端等全终端的播放次数。' },
          { name: '日增播放量', desc: '当日新增的播放次数，反映剧集当日的观看热度。' },
          { name: '累计播放量', desc: '自上线以来的累计总播放次数。' }
        ]
      },
      {
        icon: '📊',
        title: '剧力指数',
        items: [
          { name: '综合指数', desc: '基于热度、口碑、播放量、讨论度、媒体关注度五个维度，通过加权计算得出的综合评价指数，满分100。' },
          { name: '口碑维度', desc: '综合豆瓣评分、知乎推荐度、用户好评率等计算得出。' },
          { name: '讨论度维度', desc: '综合微博话题讨论量、抖音相关视频量、百度搜索指数等计算得出。' }
        ]
      },
      {
        icon: '💬',
        title: '社交数据',
        items: [
          { name: '微博数据', desc: '包含话题阅读量、讨论量、热搜上榜次数等微博平台相关数据。' },
          { name: '抖音数据', desc: '包含相关话题播放量、相关视频数量等抖音平台数据。' },
          { name: '百度数据', desc: '包含百度搜索指数、百度资讯指数等搜索平台数据。' }
        ]
      }
    ],
    faqs: [
      {
        q: '数据多久更新一次？',
        a: '实时热度数据每5分钟更新一次，播放量数据每小时更新一次，日榜/周榜/月榜数据每天凌晨更新。',
        open: false
      },
      {
        q: '为什么有些剧集没有播放量数据？',
        a: '部分平台可能不公开播放量数据，或者数据获取存在延迟。我们会尽最大努力覆盖更多数据源。',
        open: false
      },
      {
        q: '热度值是如何计算的？',
        a: '热度值是综合多个公开数据源，通过科学加权算法计算得出的综合指标，不等同于任何单一平台的热度数据。',
        open: false
      },
      {
        q: '数据与官方数据有差异怎么办？',
        a: '由于数据采集和计算方法的差异，我们的数据可能与各平台官方数据存在偏差，请以官方数据为准。本平台数据仅供参考。',
        open: false
      },
      {
        q: '豆瓣评分数据可靠吗？',
        a: '豆瓣评分数据来源于豆瓣公开数据，我们不做任何修改。评分的客观性由豆瓣平台保证。',
        open: false
      }
    ]
  },

  onLoad() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  toggleFaq(e) {
    const idx = e.currentTarget.dataset.index
    const key = `faqs[${idx}].open`
    this.setData({ [key]: !this.data.faqs[idx].open })
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 — 数据说明',
      path: '/pages/data-explanation/data-explanation'
    }
  }
})
