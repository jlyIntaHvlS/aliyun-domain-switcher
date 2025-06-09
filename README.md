# README

本文档适用于python使用flask服务对接阿里云API接口，可视化DNS解析管理，通过滑块的方式简单快速控制域名的解析状态

详情请咨询邮箱：jiaming.wang.22@eigsi.fr，不定时回复

### 展示

![image-20250609164559038](C:\Users\wangjm\AppData\Roaming\Typora\typora-user-images\image-20250609164559038.png)

### 前置条件

1、需要知道阿里云API的key，并配置在代码中（不推荐）或环境变量中，本文档配置在环境变量中

2、需要提前准备好每个域名的record_id，可通过api手册查询域名了解

3、python 版本 3.12.1

4、代码app.py



### 设置环境变量

编辑环境变量

````bash
vim ~/.bashrc
````

录入阿里云API的key，获取方式详见阿里云文档

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="xxxxxxxxxxxxxxxxxxx"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="xxxxxxxxxxxxxxxxxxx"
```

重新应用

````bash
source ~/.bashrc
````



### 使用会话保持运行

使用screen新建会话保持程序运行

```bash

```

进入会话后

```bashpython app.py
python app.py
```





### 防火墙安全（推荐）

设置访问限制（firewalld）

````bash
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="x.x.x.x" port port="xxxx" protocol="tcp" accept'
````

重启防火墙

````bash
firewall-cmd --reload
````

