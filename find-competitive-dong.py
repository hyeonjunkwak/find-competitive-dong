# -*- coding: utf-8 -*-
"""
Created on Tue May 11 04:15:34 2021

@author: user
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
import os
import glob
import requests
import jenkspy
from fiona.crs import from_string
from pyproj import CRS
from shapely.geometry import Point
from shapely.geometry import MultiPolygon, JOIN_STYLE

epsg5181_qgis = from_string("+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=500000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")

# 서울 법정동 별 상가 개수 구하기

sangga=pd.read_csv(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정\상권 프로젝트\상권 프로젝트\소상공인시장진흥공단_상가(상권)정보_서울.csv', engine='python', encoding='utf-8', sep='|')
sangga['상가 개수']=sangga.groupby(['행정동코드'])['상호명'].transform('count')
sangga1=sangga.drop_duplicates(subset='행정동코드')
sangga1=sangga1.dropna(subset=['행정동명'])
sangga1.to_csv(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정\csv 모음\서울 행정동 별 상가 개수.csv', encoding='cp949')

# 서울 행정동별 세대수 구하기

residence=pd.read_csv(r'D:\부동산 빅데이터 분석 스터디\new\행정동 별 세대수.txt', sep='\t', usecols=['자치구', '동', '전체세대수'])
residence=residence[(residence['동']!='계') & (residence['동']!='합계')]
residence['전체세대수']=[a.replace(",", "") for a in residence['전체세대수']]
residence['전체세대수']=residence['전체세대수'].astype(int)
residence.to_csv(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정\csv 모음\서울 행정동 별 세대수.csv', encoding='cp949')

# 행정동 면적 구하기
# 녹지지역은 행정동 면적에서 제외, 녹지지역이 많이 포함된 지역은 면적이 과대평가되기 때문.

green=gpd.GeoDataFrame.from_file(r'D:\부동산 빅데이터 분석 스터디\용도지역_도시지역_녹지지역_20210330\UPIS_C_UQ111(녹지지역).shp', encoding='utf-8') # 좌표계 grs80
green=green.to_crs(epsg5181_qgis)

os.chdir(r'D:\부동산 빅데이터 분석 스터디\과제\6주차 수업 과제\Flask')

hang=gpd.read_file('geojson.geojson')
hang=hang.to_crs(epsg5181_qgis)
hang['area']=hang.geometry.area

difference = gpd.overlay(hang, green, how='difference')

difference_seoul=difference[difference['sido']=='11']

difference_seoul['area']=difference_seoul.geometry.area/1000000

#%%

#주거세대, 가구 합 파일에 동 별 polygon값을 붙여줌

geometry=gpd.read_file('geojson.geojson')
geometry=geometry.to_crs(epsg5181_qgis)

sangga1['geometry']=sangga1.apply(lambda row : Point(row.경도, row.위도), axis=1)
sangga_geo=gpd.GeoDataFrame(sangga1, geometry='geometry', crs='epsg:4326')
sangga_geo=sangga_geo.to_crs(epsg5181_qgis)

sangga_geo['행정동코드']=sangga_geo['행정동코드'].astype(str)

for i in residence.index :
    for j in sangga_geo.index :
        if (sangga_geo.loc[j, '시군구명']==residence.loc[i, '자치구']) & (sangga_geo.loc[j, '행정동명']==residence.loc[i, '동']) :
            residence.loc[i,'행정동코드']=sangga_geo.loc[j, '행정동코드']

sum_of_residence=pd.merge(left=sangga_geo[['시도명', '시군구코드', '시군구명', '행정동코드', '행정동명', '상가 개수']], right=residence[['전체세대수', '행정동코드']], how='right', on='행정동코드')

geometry_sum_of_residence=pd.merge(sum_of_residence, difference_seoul[['adm_cd2', 'area', 'geometry']], how='inner', left_on='행정동코드', right_on='adm_cd2')
geometry_sum_of_residence.rename(columns={'area' : '면적(km2)'}, inplace=True)


# 지표A 계산
merge1=geometry_sum_of_residence.copy()

merge1['지표A']=merge1['상가 개수']/merge1['전체세대수']/(merge1['면적(km2)']) # 1km2당 세대수 대비 상가 개수
merge1['지표A']=round(merge1['지표A'], 4)

# Qcut으로 지표A 5등분

merge1['지표A_level'] = pd.qcut(merge1.지표A, 5, labels=['매우 적음', '적음', '보통', '많음', '매우 많음'])
merge1.columns

merge2=merge1[['시도명', '시군구코드', '시군구명', '행정동코드', '행정동명', '상가 개수', '전체세대수', '면적(km2)', '지표A', '지표A_level', 'geometry']]

#%%

# 이제 상주인구와 유동인구를 비교해보려함. 
# 해당 파일은 법정동 코드가 없고 서울시 데이터에서만 호환 가능한 상권 코드와 도로명 이름만 있어서 자료 활용이 까다로운 상태. 

# 따라서 도로명주소 DB txt 파일과 쪼인시키기

# 도로명주소 DB txt 파일 불러오기

doro_build=pd.read_csv(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정\도로명주소 DB.txt', encoding='cp949', sep='|', dtype='str', prefix = 'B', header=None)

doro_build['Road_Code']=doro_build['B1'].str[5:]
doro_build['Dong code']=doro_build['B30'].str[:8]
doro_build2=doro_build.drop_duplicates(subset='Road_Code')

# 서울시 우리마을가게 상권분석서비스(상권배후지-상주인구) 불러오기

sangjoo=pd.read_csv(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정\서울시 우리마을가게 상권분석서비스(상권배후지-상주인구).csv', engine='python', encoding='cp949', sep=',', dtype='str')
sangjoo['총_상주인구_수']=sangjoo['총_상주인구_수'].astype(int)
sangjoo['도로명 별 상주인구']=sangjoo.groupby(['상권_코드_명'])['총_상주인구_수'].transform('mean')
sangjoo1=sangjoo.drop_duplicates(subset='상권_코드_명')
sangjoo1['도로명 별 상주인구']=sangjoo1['도로명 별 상주인구'].astype(int)

# 서울시 우리마을가게 상권분석서비스(상권배후지-추정유동인구) 불러오기

moving=pd.read_csv(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정\서울시 우리마을가게 상권분석서비스(상권배후지-추정유동인구).csv', engine='python', encoding='cp949', sep=',', dtype='str')
moving['총_유동인구_수']=moving['총_유동인구_수'].astype(int)
moving['도로명 별 유동인구']=moving.groupby(['상권_코드_명'])['총_유동인구_수'].transform('mean')
moving1=moving.drop_duplicates(subset='상권_코드_명')
moving1['도로명 별 유동인구']=moving1['도로명 별 유동인구'].astype(int)

sangjoo_moving=pd.merge(sangjoo1[['상권_코드','상권_코드_명','도로명 별 상주인구']],moving1[['상권_코드_명','도로명 별 유동인구']], on='상권_코드_명')

# doro_build2 파일과 sangjoo_moving 파일 합치기

doro_build2.rename(columns={'B1' : '도로명코드', 'B2' : '도로명이름', 'B30' : '행정동코드', 'B31' : '행정동이름'}, inplace=True)
doro_name_sangjoo_moving=pd.merge(doro_build2[['도로명코드', '도로명이름','행정동코드','행정동이름']], sangjoo_moving[['상권_코드_명', '도로명 별 상주인구', '도로명 별 유동인구']], how='right', left_on='도로명이름', right_on='상권_코드_명')
doro_name_sangjoo_moving=doro_name_sangjoo_moving.dropna(subset=['행정동코드'])

# 지표B 구하기

doro_name_sangjoo_moving['지표B_도로명 별']=doro_name_sangjoo_moving['도로명 별 유동인구']/doro_name_sangjoo_moving['도로명 별 상주인구']

doro_name_sangjoo_moving['지표B']=doro_name_sangjoo_moving.groupby(['행정동코드'])['지표B_도로명 별'].transform('mean')

doro_name_sangjoo_moving2=doro_name_sangjoo_moving.drop_duplicates(subset='행정동코드')

# Qcut으로 지표B 5등분

doro_name_sangjoo_moving2['지표B_level'] = pd.qcut(doro_name_sangjoo_moving2.지표B, 5, labels=['매우 낮음', '낮음', '보통', '높음', '매우 높음'])
doro_name_sangjoo_moving2=doro_name_sangjoo_moving2[['행정동코드', '행정동이름', '지표B', '지표B_level']]


# 이제 모든 준비는 끝났으니 최종 분석 결과 도출 단계로 고고

# 두 파일 병합 후 상주인구 대비 유동인구는 많으면서 세대수 대비 상가 개수가 적은 법정동을 골라냄.

match=pd.merge(doro_name_sangjoo_moving2[['행정동코드', '지표B', '지표B_level']], merge2, on='행정동코드', how='left')

match.loc[match.지표A_level.isin(['매우 적음', '적음']) & match.지표B_level.isin(['매우 높음', '높음']), 'match'] = "True"

match2=match.loc[match['match'].notnull()]

match3=match2[['시도명', '시군구코드', '시군구명', '행정동코드', '행정동명', '지표A', '지표A_level', '지표B', '지표B_level', 'geometry']]
match3.reset_index(inplace=True)
del match3['index']

match3=gpd.GeoDataFrame(match3, geometry='geometry')

match3=match3.to_crs('epsg:4326')
match3.plot()

os.chdir(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정')

import folium

lat = 37.55
long = 127

m = folium.Map([lat,long],zoom_start=11, title='Competitive')

for _, r in match3.iterrows():
    
    # simplify를 쓰나 안쓰나 차이는 별로 없으나 geopandas 원문에서 쓰라고 하니 써주자
    
    sim_geo = gpd.GeoSeries(r['geometry']).simplify(tolerance=0.001)
    geo_j = sim_geo.to_json()
    geo_j = folium.GeoJson(data=geo_j,
                           style_function = lambda x: {'fillColor': 'blue'})
    # folium.Popup(r['법정동명']).add_to(geo_j)
    geo_j.add_to(m)

m.save('competitive.html')

# 최종 결과 파일 저장

match3.to_csv(r'D:\부동산 빅데이터 분석 스터디\상권 프로젝트 수정\최종 매칭.csv', encoding='cp949', sep = ',')
