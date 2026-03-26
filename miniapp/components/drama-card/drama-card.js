Component({
  properties: {
    drama: {
      type: Object,
      value: {}
    },
    showHeat: {
      type: Boolean,
      value: true
    },
    showScore: {
      type: Boolean,
      value: true
    },
    rank: {
      type: Number,
      value: 0
    }
  },

  methods: {
    onTap() {
      const { id } = this.data.drama
      if (!id) return
      wx.navigateTo({
        url: `/pages/drama-detail/drama-detail?id=${id}`
      })
    }
  }
})
