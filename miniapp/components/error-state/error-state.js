Component({
  properties: {
    text: {
      type: String,
      value: '加载失败'
    },
    showRetry: {
      type: Boolean,
      value: true
    }
  },

  methods: {
    onRetryTap() {
      this.triggerEvent('retry')
    }
  }
})
