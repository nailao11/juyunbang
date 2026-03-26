const { formatNumber, formatChange } = require('../../utils/format')

Component({
  properties: {
    data: {
      type: Array,
      value: []
    },
    title: {
      type: String,
      value: '近30日播放量趋势'
    }
  },

  data: {
    displayData: [],
    expanded: false,
    defaultCount: 10
  },

  observers: {
    'data': function (data) {
      this._computeDisplayData(data)
    }
  },

  lifetimes: {
    attached() {
      this._computeDisplayData(this.data.data)
    }
  },

  methods: {
    _computeDisplayData(data) {
      if (!data || !data.length) {
        this.setData({ displayData: [] })
        return
      }

      const maxValue = Math.max(...data.map(item => item.value || 0))
      const safeMax = maxValue > 0 ? maxValue : 1

      // Sort by index to find top 3 values
      const sorted = data.map((item, idx) => ({ value: item.value || 0, idx }))
        .sort((a, b) => b.value - a.value)
      const top3Set = new Set(sorted.slice(0, 3).map(s => s.idx))

      const displayData = data.map((item, idx) => {
        const value = item.value || 0
        const barWidth = Math.max((value / safeMax) * 100, 2)
        const formattedValue = formatNumber(value)
        const changeText = formatChange(item.change_rate)

        let changeDir = ''
        if (item.change_rate > 0) changeDir = 'up'
        else if (item.change_rate < 0) changeDir = 'down'

        return {
          date: item.date || '',
          value: value,
          barWidth: barWidth,
          formattedValue: formattedValue,
          changeText: changeText,
          changeDir: changeDir,
          isTop3: top3Set.has(idx)
        }
      })

      this.setData({ displayData })
    },

    onToggleExpand() {
      this.setData({ expanded: !this.data.expanded })
    }
  }
})
