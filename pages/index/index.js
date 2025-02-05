Page({
    data: {
      items: [
        { 
          id: 1,
          title: "餐厅点餐",
          scenario: "restaurant",
          prompt: "你是一个香港茶餐厅的服务员，需要用简单粤语与顾客对话，顾客是个来自中国内地的粤语初学者。对话应围绕点餐流程展开，包括推荐招牌菜、询问需求、处理特殊要求等。注意使用香港地道用语。现在请你用1-2句话开启对话。"
        },
        {
          id: 2,
          title: "街头问路", 
          scenario: "street",
          prompt: "你是一个热心的香港市民，需要用简单粤语为游客指路。对话应包含地点确认、路线描述、地标提示等要素。注意使用香港街道常见名称。"
        },
        // 其他两个场景类似结构
      ]
    },
    onLoad() {
      console.log("页面加载成功");
    },
    goToScene(e) {
      const { scenario, prompt } = e.currentTarget.dataset;
      wx.navigateTo({
        url: `/pages/scene/scene?scenario=${scenario}&prompt=${encodeURIComponent(prompt)}`
      });
    }
  });
  