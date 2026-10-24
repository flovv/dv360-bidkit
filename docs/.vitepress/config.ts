import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/dv360-bidkit/',
  title: "DV360 BidKit",
  description: "Production-Grade Algorithm Compiler, Linter, and Simulator for Google DV360 Custom Bidding",
  markdown: {
    math: true
  },
  head: [
    ['meta', { name: 'theme-color', content: '#1a73e8' }],
    ['script', { type: 'application/ld+json' }, JSON.stringify({
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "name": "DV360 BidKit",
      "applicationCategory": "DeveloperApplication",
      "operatingSystem": "Linux, macOS, Windows",
      "description": "Python-native compiler, AST validator, and pre-flight evaluation simulator for Google Display & Video 360 (DV360) custom bidding algorithms.",
      "installUrl": "https://github.com/flovv/dv360-bidkit",
      "offers": {
        "@type": "Offer",
        "price": "0.00",
        "priceCurrency": "EUR"
      }
    })]
  ],
  themeConfig: {
    siteTitle: 'DV360 BidKit',
    search: {
      provider: 'local'
    },
    nav: [
      { text: 'Documentation', link: '/' },
      { text: 'Research Foundations', link: '/algorithmic_research_foundations' },
      { text: 'LLM Guide', link: '/llms.txt' },
      { text: 'GitHub', link: 'https://github.com/flovv/dv360-bidkit' }
    ],
    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: 'Overview & Architecture', link: '/' },
          { text: 'Algorithmic Foundations', link: '/algorithmic_research_foundations' },
        ]
      },
      {
        text: 'AI & LLM Integration',
        items: [
          { text: 'llms.txt (API Summary)', link: '/llms.txt' },
          { text: 'llms-full.txt (Full Context)', link: '/llms-full.txt' },
        ]
      }
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/flovv/dv360-bidkit' }
    ],
    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2026 DV360 BidKit Contributors'
    }
  }
})
