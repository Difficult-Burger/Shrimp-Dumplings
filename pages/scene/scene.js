const LOCAL_IP = '192.168.56.1'; 

// 新增封装：返回 Promise 的 wx.request
function requestPromise(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      ...options,
      header: {
        "content-type": "application/json",
        ...(options.header || {})
      },
      success: (res) => resolve(res),
      fail: (err) => reject(err)
    });
  });
}

Page({
    data: {
      currentScenario: "",
      systemPrompt: "",
      messages: [
        { text: "我想了解一下关于聊天界面的设计。", type: "user" },
        { text: "当然可以！聊天界面通常包括消息列表、输入框和发送按钮。", type: "bot" }
      ],
      inputValue: ""
    },
  
    onLoad(options) {
      console.log("当前场景参数:", options);
      wx.request({
        url: `http://${LOCAL_IP}:5000/health`,
        success: () => console.log("服务正常"),
        fail: () => console.log("服务不可用")
      });
      this.setData({
        currentScenario: options.scenario,
        systemPrompt: decodeURIComponent(options.prompt),
        messages: []  // 清空历史对话
      });
      // 自动初始化，让 AI 说第一句话
      this.initializeScenario();
    },
  
    async initializeScenario() {
      wx.showLoading({ title: '初始化中...' });
      try {
         const res = await requestPromise({
           url: `http://${LOCAL_IP}:5000/init`,
           method: 'POST',
           data: { prompt: this.data.systemPrompt },
           timeout: 70000
         });
         wx.hideLoading();
         if (res.statusCode === 200 && res.data && res.data.response) {
             this.setData({
               messages: [{ text: res.data.response, type: "bot" }]
             });
         } else {
             wx.showToast({ title: "初始化失败", icon: "none" });
             this.setData({
               messages: [{ text: "初始化失败", type: "bot" }]
             });
         }
      } catch (error) {
         wx.hideLoading();
         wx.showToast({ title: `初始化失败: ${error.message || '未知错误'}`, icon: "none" });
         this.setData({
           messages: [{ text: "初始化失败，请稍后重试", type: "bot" }]
         });
      }
    },
  
    // 处理输入框输入
    handleInput(e) {
      this.setData({ inputValue: e.detail.value });
    },
  
    // 发送消息
    async sendMessage() {
      try {
        const { inputValue, messages } = this.data;
        if (!inputValue.trim()) return;
  
        // 用户消息
        this.setData({
          messages: [...messages, { text: inputValue, type: "user" }],
          inputValue: ""
        });
  
        // 调用后端API（增加加载状态）
        wx.showLoading({ title: '发送中...', mask: true });
        
        const res = await requestPromise({
          url: `http://${LOCAL_IP}:5000/chat`,
          method: 'POST',
          data: {
            scenario: this.data.currentScenario,
            message: inputValue,
            history: this.data.messages
          },
          timeout: 70000  // 调整为70秒
        });
  
        wx.hideLoading();
  
        // 处理错误响应
        if (res.statusCode !== 200) {
          const errorMsg = res.data?.error || `请求失败: ${res.statusCode}`;
          throw new Error(errorMsg);
        }
  
        // AI回复
        if (res.data.response) {
          let responseText = res.data.response;
          // 处理截断提示
          if (res.data.warning === 'reply_truncated') {
            responseText += '\n（系统提示：回复因长度限制被截断）';
          }
          
          this.setData({
            messages: [...this.data.messages, { 
              text: responseText,
              type: "bot" 
            }]
          });
        }
      } catch (error) {
        wx.hideLoading();
        console.error('发送消息出错:', error);
        
        // 更友好的错误提示
        let errorMsg = (error.message || error.errMsg || '未知错误');
        if ((error.message || '').includes('timed out') || (error.errMsg || '').includes('timeout')) {
          errorMsg = '回复超时，请稍后再试';
        } else if ((error.message || '').includes('500')) {
          errorMsg = '服务暂时不可用';
        }

        wx.showToast({ 
          title: `发送失败: ${errorMsg}`,
          icon: 'none',
          duration: 3000
        });
        
        // 保留用户最后输入
        this.setData({ inputValue: this.data.inputValue });
      }
    }
  });
  