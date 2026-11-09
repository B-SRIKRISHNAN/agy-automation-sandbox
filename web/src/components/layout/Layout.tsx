import React from 'react';
import { Header } from './Header';
import { BottomNav, type TabType } from './BottomNav';

interface LayoutProps {
  children: React.ReactNode;
  activeTab: TabType;
  onChangeTab: (tab: TabType) => void;
}

export function Layout({ children, activeTab, onChangeTab }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Header />
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-4 pb-24 md:pb-8">
        {children}
      </main>
      <div className="md:hidden">
        <BottomNav activeTab={activeTab} onChangeTab={onChangeTab} />
      </div>
    </div>
  );
}
