import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const cinematicSelector = [
  '.home-hero', '.dreaming-showcase', '.product-footer', '.compass-focus', '.idea-field',
  '.journey-hero', '.journey-path', '.calendar-board', '.footprint-board',
  '.library-header', '.library-dashboard',
].join(',')

export function ScrollDirector() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
    const updateProgress = () => {
      const available = Math.max(1, document.documentElement.scrollHeight - window.innerHeight)
      const progress = Math.min(1, Math.max(0, window.scrollY / available))
      document.documentElement.style.setProperty('--page-scroll', progress.toFixed(4))
    }
    const sections = Array.from(document.querySelectorAll<HTMLElement>(cinematicSelector))
    sections.forEach((section, index) => {
      section.classList.add('scroll-cinematic')
      section.style.setProperty('--section-index', String(index))
    })
    let observer: IntersectionObserver | undefined
    if ('IntersectionObserver' in window) {
      observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) entry.target.classList.add('is-visible')
        })
      }, { rootMargin: '-8% 0px -10%', threshold: 0.12 })
      sections.forEach((section) => observer?.observe(section))
    } else {
      sections.forEach((section) => section.classList.add('is-visible'))
    }
    updateProgress()
    window.addEventListener('scroll', updateProgress, { passive: true })
    window.addEventListener('resize', updateProgress)
    return () => {
      observer?.disconnect()
      window.removeEventListener('scroll', updateProgress)
      window.removeEventListener('resize', updateProgress)
    }
  }, [pathname])

  return <div className="scroll-telemetry" aria-hidden="true"><span /></div>
}
