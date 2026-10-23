import type { ReactNode } from 'react';
import { ConfigProvider, type ThemeConfig } from 'antd';
import ruRU from 'antd/locale/ru_RU';

const theme: ThemeConfig = {
  token: {
    colorPrimary: '#ef3124',
    colorInfo: '#ef3124',
    colorText: '#24272b',
    colorTextSecondary: '#747982',
    colorBgLayout: '#f2f3f5',
    fontFamily: 'Arial, Helvetica, sans-serif',
    fontSize: 13,
    borderRadius: 8,
    controlHeight: 40,
  },
  components: {
    Button: { primaryShadow: 'none', defaultShadow: 'none' },
    Menu: {
      itemBg: 'transparent',
      itemHeight: 36,
      itemMarginInline: 0,
      itemMarginBlock: 1,
      itemBorderRadius: 7,
      itemSelectedBg: '#ffffff',
      itemSelectedColor: '#bd2a25',
      itemHoverBg: '#e8eaed',
      iconSize: 17,
      fontSize: 11,
    },
    Card: { borderRadiusLG: 16 },
    Tabs: { horizontalItemGutter: 24 },
  },
};

export function UiProvider({ children }: { children: ReactNode }) {
  return <ConfigProvider locale={ruRU} theme={theme}>{children}</ConfigProvider>;
}
