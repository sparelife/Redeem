# -*- coding: utf-8 -*-

import os
import json
import datetime
import numpy as np
import pandas as pd
import pymc3 as pm

import arviz as az
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager
# 支持中文（Noto Sans CJK SC，同 harpoon.py 的字体方案）
for _f in ['~/.fonts/NotoSansCJKSC-Regular.ttf', '~/.fonts/NotoSansCJKSC-Bold.ttf']:
    _p = os.path.expanduser(_f)
    if os.path.exists(_p):
        matplotlib.font_manager.fontManager.addfont(_p)
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ── 采样参数配置 ──────────────────────────────────────────
BAYESTIME_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bayestime_config.json')

def load_sampling_config():
    """读取 bayestime_config.json，返回采样参数字典（draws/tune/chains 等）"""
    if not os.path.exists(BAYESTIME_CONFIG):
        print("错误：未找到配置文件 %s" % BAYESTIME_CONFIG)
        print("请创建该文件，内容示例：")
        print('  {"draws": 2000, "tune": 1000, "chains": 2}')
        exit(1)
    with open(BAYESTIME_CONFIG) as f:
        return json.load(f)

def fectch_data(filein):
    quit_jsl_df = pd.read_excel(filein,'jsl')
    quit_jsl_df = quit_jsl_df[~quit_jsl_df['名称'].str.endswith('EB')]
    quit_jsl_df = quit_jsl_df.dropna(subset=['存续年限'])  # 存续年限缺失的记录无法建模，丢弃

    df = quit_jsl_df[['存续年限','退市原因']]
    # 将退市原因编码成数字格式
    df['退市原因编码'] = df['退市原因'].apply(lambda x: 1 if x == "强赎" else 0)  # 强赎 = 1, 到期 = 0
    return df

if __name__ == '__main__':
    from sys import argv
    filein = ""
    if len(argv) > 1:
        filein = argv[1]
    else:
        print("please run like 'python redeem.py [file]'")
        exit(1)


    redeem_df = fectch_data(filein)

    cfg = load_sampling_config()
    print("采样参数: " + json.dumps(cfg, ensure_ascii=False))

    years = redeem_df['存续年限'].values
    reasons = redeem_df['退市原因编码'].values

    # 使用 PyMC3 定义逻辑回归模型
    with pm.Model() as model:
        # 先验概率
        alpha = pm.Normal('alpha', mu=0, sigma=10)
        beta = pm.Normal('beta', mu=0, sigma=10)
    
        # 逻当我们使用逻辑回归模型时，背后的直觉是存续年限（years）和强赎的概率（p）之间可能存在某种线性关系。
        # 不过，由于概率 p 是0到1之间的值，我们需要通过某种方式将线性预测值映射到[0, 1]的区间。
        # Sigmoid函数（逻辑函数）正是用来实现这种映射的
        p = pm.Deterministic('p', pm.math.sigmoid(alpha + beta * years))
    
        #使用Bernoulli似然函数，这是因为退市原因是一个二分类变量：强赎（编码为1）和到期（编码为0）
        #如果我们有基于某些解释变量（如存续年限）来预测一个事件会不会发生，那么Bernoulli分布是合适的选择
        likelihood = pm.Bernoulli('likelihood', p=p, observed=reasons)
        
        # 采样（参数来自 bayestime_config.json）
        trace = pm.sample(draws=cfg.get('draws', 2000),
                          tune=cfg.get('tune', 1000),
                          chains=cfg.get('chains', 2),
                          random_seed=cfg.get('random_seed'),
                          return_inferencedata=False)

    # 获取后验概率分布
    posterior_alpha = trace['alpha']
    posterior_beta = trace['beta']
  
    # 定义不同存续时间条件
    years_range = np.linspace(min(years), max(years), 72)
    
    # 计算不同存续时间条件下的强赎后验概率
    posterior_p = np.array([pm.math.sigmoid(posterior_alpha[i] + posterior_beta[i] * years_range).eval() for i in range(len(posterior_alpha))])
    print(f"length of posterior_p:{len(posterior_p)},length of posterior_alpha:{len(posterior_alpha)}")
    
    # 计算每个时间点上的中位数
    median_p = np.median(posterior_p, axis=0)

    # 绘制不同存续时间条件下的强赎后验概率分布
    #posterior_p 是一个矩阵，它包含了从后验分布中采样得到的不同存续年限下的强赎概率。
    #矩阵的每一列对应 years_range 中的一个存续年限，每一行对应一组模型参数的采样结果
    plt.fill_between(years_range, np.percentile(posterior_p, 2.5, axis=0), np.percentile(posterior_p, 97.5, axis=0), alpha=0.5)
    plt.plot(years_range, median_p, label='后验概率中位数')
    plt.xlabel('存续年限')
    plt.ylabel('强赎后验概率')
    plt.legend()
    plt.title('不同存续时间条件下的强赎后验概率分布')
    plt.savefig("bayes.png")
    plt.show()

    # 打印退市原因为强赎的后验概率均值和95%后验概率区间
    posterior_hpd = az.hdi(posterior_p, hdi_prob=0.95)
    print(f"median_p个数:{len(median_p)},posterior_hpd个数:{len(posterior_hpd)}")
    
    [ print(f"{years_range[i]},{median_p[i]},{posterior_hpd[i]}") for i in range(len(years_range)) ]

    # 生成并保存"存续年限 - 强赎后验概率中位数"表格（存续年限保留 1 位小数，同一年取均值去重）
    bayes_df = pd.DataFrame({
        '存续年限': np.round(years_range, 1),
        '强赎后验概率中位数': np.round(median_p, 4),
    })
    bayes_df = bayes_df.groupby('存续年限', as_index=False)['强赎后验概率中位数'].mean()
    tnow = datetime.datetime.now()
    fileout = tnow.strftime('%Y_%m_%d') + '_bayes.xlsx'
    # 存续年限列用 "0.0" 数字格式，保证 1 显示为 1.0
    with pd.ExcelWriter(fileout, engine='openpyxl') as writer:
        bayes_df.to_excel(writer, index=False, sheet_name='bayes')
        ws = writer.sheets['bayes']
        for row in range(2, len(bayes_df) + 2):
            ws.cell(row=row, column=1).number_format = '0.0'
    print("bayes table of path:" + fileout)
    print(bayes_df.to_string())
   