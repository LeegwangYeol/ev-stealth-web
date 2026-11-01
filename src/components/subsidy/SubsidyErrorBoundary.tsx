'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class SubsidyErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Subsidy Component Error Boundary caught exception:', error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          aria-live="assertive"
          className="p-6 rounded-3xl bg-slate-950 border border-rose-500/50 text-slate-200 text-center space-y-4 my-4 shadow-xl"
        >
          <div className="w-12 h-12 mx-auto rounded-2xl bg-rose-950/80 border border-rose-500/40 text-rose-300 flex items-center justify-center text-2xl" aria-hidden="true">
            ⚠️
          </div>
          <div className="space-y-1">
            <h3 className="text-base sm:text-lg font-bold text-white">
              {this.props.fallbackTitle || '보조금 계산 중 오류가 발생했습니다'}
            </h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              입력값 또는 지자체 쿼터 데이터를 처리하는 과정에서 일시적인 예외가 발생했습니다.
              {this.state.error?.message ? ` (${this.state.error.message})` : ''}
            </p>
          </div>
          <button
            type="button"
            onClick={this.handleReset}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
          >
            🔄 다시 계산 시도
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
