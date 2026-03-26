Component({
  properties: {
    image: {
      type: String,
      value: '/images/default/empty.png'
    },
    text: {
      type: String,
      value: '暂无数据'
    },
    showButton: {
      type: Boolean,
      value: false
    },
    buttonText: {
      type: String,
      value: '刷新试试'
    }
  },

  methods: {
    onButtonTap() {
      this.triggerEvent('refresh')
    }
  }
})
