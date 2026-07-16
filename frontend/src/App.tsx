import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from './components/Layout/MainLayout';
import HomePage from './pages/HomePage';
import ReportPage from './pages/ReportPage';
import QAPage from './pages/QAPage';
import PPTPage from './pages/PPTPage';
import HistoryPage from './pages/HistoryPage';
import LogPage from './pages/LogPage';

const App: React.FC = () => {
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <MainLayout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/qa" element={<QAPage />} />
            <Route path="/ppt" element={<PPTPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/logs" element={<LogPage />} />
          </Routes>
        </MainLayout>
      </Router>
    </ConfigProvider>
  );
};

export default App;
