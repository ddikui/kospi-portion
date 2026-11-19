# 코스피 시가총액 비중 (KOSPI Market Cap Portion)

코스피 상장 종목들의 시가총액과 전체 대비 비중, 상위 종목 집중도를 한눈에 확인할 수 있는 실시간 웹 애플리케이션입니다.

## 주요 기능
- 코스피 상장 종목 시가총액 순위 및 비중 계산
- 상위 종목(1위, 5위, 10위, 30위) 시가총액 쏠림 현황 표시
- 보통주 / 우선주 필터링 및 종목 검색, 정렬 기능
- Vercel Serverless Function을 통한 자동 시세 API 및 Edge CDN 캐싱 지원
- 반응형 웹 디자인 지원

## 배포 방법

### Vercel 배포 (추천)
1. GitHub 저장소에 코드를 푸시합니다.
2. [Vercel 대시보드](https://vercel.com)에 로그인 후 **Add New Project**를 클릭합니다.
3. 이 GitHub 저장소(`kospi-portion`)를 **Import**합니다.
4. 별도 설정 변경 없이 **Deploy** 버튼을 누르면 배포가 완료됩니다!
   - 정적 프론트엔드는 `public/`에서 서빙됩니다.
   - 시세 API는 Vercel Serverless Function(`api/market.py`)으로 동작하며 Edge CDN에 3분간 자동 캐싱됩니다.

### 로컬 실행
```bash
python3 server.py
```
브라우저에서 [http://127.0.0.1:8787](http://127.0.0.1:8787)으로 접속합니다.
