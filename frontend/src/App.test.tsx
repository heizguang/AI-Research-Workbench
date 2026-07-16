import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders app title', () => {
  render(<App />);
  const titleElement = screen.getByText(/多智能体报告生成系统/i);
  expect(titleElement).toBeInTheDocument();
});

test('renders home page by default', () => {
  render(<App />);
  const homeElement = screen.getByText(/首页/i);
  expect(homeElement).toBeInTheDocument();
});
