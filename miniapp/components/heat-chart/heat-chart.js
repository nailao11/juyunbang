Component({
  properties: {
    data: {
      type: Array,
      value: []
    },
    title: {
      type: String,
      value: '今日热度走势'
    },
    height: {
      type: Number,
      value: 200
    }
  },

  observers: {
    'data, height': function () {
      this._calcBars()
    }
  },

  lifetimes: {
    attached() {
      this._calcBars()
    }
  },

  methods: {
    _calcBars() {
      const { data, height } = this.data
      if (!data || !data.length) {
        this.setData({ bars: [], maxLabel: '', minLabel: '', hasData: false })
        return
      }

      const values = data.map(function (d) { return d.value || 0 })
      const maxVal = Math.max.apply(null, values)
      const minVal = Math.min.apply(null, values)
      const lastIndex = data.length - 1

      // Reserve some top padding so max bar doesn't touch the top
      var maxBarHeight = height * 0.85

      var bars = data.map(function (item, index) {
        var ratio = maxVal > 0 ? (item.value / maxVal) : 0
        var barHeight = Math.max(ratio * maxBarHeight, 4) // minimum 4rpx
        var showLabel = index % 3 === 0 || index === lastIndex
        return {
          time: item.time || '',
          value: item.value || 0,
          barHeight: barHeight,
          showLabel: showLabel,
          isLatest: index === lastIndex
        }
      })

      this.setData({
        bars: bars,
        maxLabel: this._formatValue(maxVal),
        minLabel: this._formatValue(minVal),
        hasData: true
      })
    },

    _formatValue(val) {
      if (val >= 10000) {
        return (val / 10000).toFixed(1) + '万'
      }
      return String(val)
    }
  }
})
