const LOCAL_IP = '10.8.17.75'; 
const BASE_URL = 'https://20040415.xyz';

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
  
    // 用于存储当前的 socketTask
    socketTask: null,
  
    onLoad(options) {
      console.log("当前场景参数:", options);
      wx.request({
        url: `${BASE_URL}/health`,
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
           url: `${BASE_URL}/init`,
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
      const value = e.detail.value.replace(/\s+/g, ' ').trimStart();  // 合并连续空格
      this.setData({ inputValue: value });
    },
  
    // 统一管理 WebSocket 连接：若存在未关闭的连接，则先关闭
    closeSocketIfNeeded() {
      if (this.socketTask) {
        wx.closeSocket({
          complete: () => {
            console.log('上次连接已关闭');
            this.socketTask = null;
          }
        });
      }
    },
  
    // 发送消息，并实时显示 AI 回复
    sendMessage() {
      const { inputValue, messages, currentScenario } = this.data;
      if (!inputValue.trim()) return;
  
      // 添加用户消息
      this.setData({
        messages: [...messages, { text: inputValue, type: "user" }],
        inputValue: ""
      }, () => {  // 添加回调函数
        // 在这里执行 WebSocket 连接和消息发送
        this.connectAndSendMessage();
      });
    },
  
    // 新增独立方法
    connectAndSendMessage() {
      const { currentScenario, messages } = this.data;
      // 这里获取的是更新后的 messages（不包含刚添加的用户消息）
      const payload = {
        scenario: currentScenario,
        message: this.data.inputValue, // 此时已清空，需要保存旧值
        history: messages.slice(0, -1)  // 排除刚添加的用户消息
      };
      // 如果有未关闭的连接，先关闭它
      this.closeSocketIfNeeded();
  
      // 先建立连接
      this.socketTask = wx.connectSocket({
        url: `wss://flask-65op-137747-10-1339695968.sh.run.tcloudbase.com/ws/chat`,
        header: {
          'Sec-WebSocket-Extensions': 'null'  // 显式禁用扩展
        }
      });
  
      // 再注册事件
      this.socketTask.onOpen(() => {
        console.log('连接已建立');
        this.socketTask.send({
          data: JSON.stringify(payload),
          success: () => console.log("消息发送成功"),
          fail: (err) => console.error("消息发送失败", err)
        });
      });
  
      this.socketTask.onMessage((res) => {
        try {
          // 修改后：直接使用文本内容
          const content = res.data;
          if (content) {
            let msgs = this.data.messages;
            if (msgs.length === 0 || msgs[msgs.length - 1].type !== "bot") {
              msgs.push({ text: content, type: "bot" });
            } else {
              msgs[msgs.length - 1].text += content;
            }
            this.setData({ messages: msgs });
          }
        } catch (e) {
          console.error("消息解析失败:", e);
        }
      });
  
      wx.onSocketError((res) => {
        console.error("WebSocket 错误详情:", res);
        wx.showToast({ title: `Socket错误: ${res.errMsg}`, icon: 'none', duration: 3000 });
        wx.closeSocket(); // 出错时关闭连接
      });
    }
  });
  