const { formatHeat, formatNumber, formatChange, formatStatus } = require('../../utils/format')

Component({
  properties: {
    item: {
      type: Object,
      value: {}
    },
    rank: {
      type: Number,
      value: 0
    },
    maxValue: {
      type: Number,
      value: 1
    },
    valueType: {
      type: String,
      value: 'heat'
    }
  },

  observers: {
    'item, maxValue, valueType': function () {
      this._updateDisplay()
    }
  },

  lifetimes: {
    attached() {
      this._updateDisplay()
    }
  },

  methods: {
    _updateDisplay() {
      const { item, maxValue, valueType } = this.data
      if (!item) return

      const isHeat = valueType === 'heat'
      const rawValue = isHeat ? item.heat_value : item.play_count
      const displayValue = isHeat ? formatHeat(rawValue) : formatNumber(rawValue)
      const valueLabel = isHeat ? '热度' : '播放量'
      const changeText = formatChange(item.change_rate)
      const statusText = formatStatus(item.status)

      const safeMax = maxValue > 0 ? maxValue : 1
      const progressWidth = rawValue ? Math.min((rawValue / safeMax) * 100, 100) : 0

      let changeDir = ''
      if (item.change_rate > 0) changeDir = 'up'
      else if (item.change_rate < 0) changeDir = 'down'

      this.setData({
        displayValue,
        valueLabel,
        changeText,
        changeDir,
        statusText,
        progressWidth
      })
    },

    onTap() {
      const { item } = this.data
      if (!item || !item.id) return
      wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${item.id}` })
    }
  }
})
