'use client';

import React, { Component, ErrorInfo, ReactNode, createRef } from 'react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  boundaryId?: string;
  retryLabel?: string;
  headingLevel?: 'h2' | 'h3';
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

export default class SubsidyErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    retryCount: 0,
  };

  private containerRef = createRef<HTMLDivElement>();
  private retryButtonRef = createRef<HTMLButtonElement>();

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Subsidy Component Error Boundary caught exception:', error, errorInfo);
  }

  public componentDidMount() {
    if (this.state.hasError) {
      if (this.retryButtonRef.current) {
        this.retryButtonRef.current.focus();
      } else if (this.containerRef.current) {
        this.containerRef.current.focus();
      }
    }
  }

  public componentDidUpdate(_prevProps: Props, prevState: State) {
    // When entering error state, shift programmatic focus to retry button or container for screen reader & keyboard accessibility
    if (!prevState.hasError && this.state.hasError) {
      if (this.retryButtonRef.current) {
        this.retryButtonRef.current.focus();
      } else if (this.containerRef.current) {
        this.containerRef.current.focus();
      }
    }
  }

  public handleReset = () => {
    this.setState((prevState) => ({
      hasError: false,
      error: null,
      retryCount: prevState.retryCount + 1,
    }));
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  private handleReload = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  private handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    // Keyboard dismissibility: Escape key dismisses/resets the error boundary
    if (e.key === 'Escape') {
      e.preventDefault();
      this.handleReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      const baseId = String(this.props.boundaryId || 'subsidy-error').trim().replace(/\s+/g, '-') || 'subsidy-error';
      const titleId = `${baseId}-title`;
      const descId = `${baseId}-desc`;
      const HeadingTag = this.props.headingLevel === 'h2' ? 'h2' : 'h3';
      const retryText = this.props.retryLabel || '다시 계산 시도';
      const rawMsg =
        typeof this.state.error?.message === 'string'
          ? this.state.error.message.replace(/\s+/g, ' ').trim()
          : '';
      const safeErrorMessage = rawMsg.length > 160 ? `${rawMsg.slice(0, 157)}...` : rawMsg;

      return (
        <div
          ref={this.containerRef}
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          aria-labelledby={titleId}
          aria-describedby={descId}
          tabIndex={-1}
          onKeyDown={this.handleKeyDown}
          className="p-6 rounded-3xl bg-slate-950 border border-rose-500/50 text-slate-200 text-center space-y-4 my-4 shadow-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
        >
          <div className="w-12 h-12 mx-auto rounded-2xl bg-rose-950/80 border border-rose-500/40 text-rose-300 flex items-center justify-center text-2xl" aria-hidden="true">
            ⚠️
          </div>
          <div className="space-y-1">
            <HeadingTag id={titleId} className="text-base sm:text-lg font-bold text-white">
              {this.props.fallbackTitle || '보조금 계산 중 오류가 발생했습니다'}
            </HeadingTag>
            <p id={descId} className="text-xs text-slate-300 max-w-md mx-auto leading-relaxed">
              입력값 또는 지자체 쿼터 데이터를 처리하는 과정에서 일시적인 예외가 발생했습니다.
              {safeErrorMessage ? ` (${safeErrorMessage})` : ''}
            </p>
          </div>
          <div className="flex items-center justify-center gap-2 flex-wrap">
            <button
              ref={this.retryButtonRef}
              type="button"
              onClick={this.handleReset}
              aria-label={retryText === '다시 계산 시도' ? '보조금 계산 다시 시도' : retryText}
              className="px-4 py-2.5 min-h-[44px] min-w-[44px] inline-flex items-center justify-center gap-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
            >
              <span aria-hidden="true">🔄</span>
              <span>{retryText}</span>
            </button>
            {this.state.retryCount > 0 && (
              <button
                type="button"
                onClick={this.handleReload}
                aria-label="페이지 새로고침"
                className="px-4 py-2.5 min-h-[44px] min-w-[44px] inline-flex items-center justify-center gap-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-500 text-xs font-semibold shadow transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              >
                <span aria-hidden="true">🔃</span>
                <span>새로고침</span>
              </button>
            )}
          </div>
        </div>
      );
    }

    return (
      <React.Fragment key={this.state.retryCount}>
        {this.props.children}
      </React.Fragment>
    );
  }
}
