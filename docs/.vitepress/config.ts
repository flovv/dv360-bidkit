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
      { text: 'Documentation', link: '/quickstart' },
      { text: 'Research Foundations', link: '/algorithmic_research_foundations' },
      { text: 'Pro Commercial', link: '/pro' },
      { text: 'Agent Skill', link: '/agent_skill' },
      { text: 'Get Pro License', link: 'https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT' },
      { text: 'GitHub', link: 'https://github.com/flovv/dv360-bidkit' }
    ],
    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: 'Overview & Architecture', link: '/' },
          { text: 'Quickstart & CLI Guide', link: '/quickstart' },
          { text: 'Algorithmic Foundations', link: '/algorithmic_research_foundations' },
        ]
      },
      {
        text: 'Commercial Extension',
        items: [
          { text: 'DV360 BidKit Pro & Polar', link: '/pro' },
        ]
      },
      {
        text: 'AI & Developer Integration',
        items: [
          { text: 'Agent Skill (dv360-custom-bidding)', link: '/agent_skill' },
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
