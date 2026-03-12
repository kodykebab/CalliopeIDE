import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function TestResponsive() {
  const [screenSize, setScreenSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const updateSize = () => {
      setScreenSize({ width: window.innerWidth, height: window.innerHeight })
    }
    
    updateSize()
    window.addEventListener('resize', updateSize)
    return () => window.removeEventListener('resize', updateSize)
  }, [])

  const getBreakpointInfo = (width) => {
    if (width < 640) return { name: 'Mobile', class: 'sm', color: 'bg-red-500' }
    if (width < 768) return { name: 'Small', class: 'md', color: 'bg-yellow-500' }
    if (width < 1024) return { name: 'Tablet', class: 'lg', color: 'bg-blue-500' }
    return { name: 'Desktop', class: 'xl', color: 'bg-green-500' }
  }

  const breakpoint = getBreakpointInfo(screenSize.width)

  return (
    <div className="min-h-screen bg-[#0D1117] text-white p-4">
      {/* Responsive Test Header */}
      <div className="mb-8">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4">
          Mobile Responsiveness Test
        </h1>
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          <div className={`px-3 py-1 rounded ${breakpoint.color} text-white text-sm font-medium`}>
            {breakpoint.name} ({breakpoint.class})
          </div>
          <div className="text-gray-400">
            {screenSize.width} × {screenSize.height}
          </div>
        </div>
      </div>

      {/* Breakpoint Tests */}
      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold mb-4">Layout Tests</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="p-4 bg-[#161B22] border border-gray-700 rounded">
              <h3 className="font-medium mb-2">Responsive Grid</h3>
              <p className="text-sm text-gray-400">
                1 column on mobile, 2 on tablet, 3 on desktop
              </p>
            </div>
            <div className="p-4 bg-[#161B22] border border-gray-700 rounded">
              <h3 className="font-medium mb-2">Card 2</h3>
              <p className="text-sm text-gray-400">
                Content adapts to grid layout
              </p>
            </div>
            <div className="p-4 bg-[#161B22] border border-gray-700 rounded">
              <h3 className="font-medium mb-2">Card 3</h3>
              <p className="text-sm text-gray-400">
                Third card shows on desktop only
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">Navigation Test</h2>
          <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center p-4 bg-[#161B22] border border-gray-700 rounded">
            <div className="text-sm font-medium">Calliope IDE</div>
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 w-full sm:w-auto">
              <Button size="sm" className="w-full sm:w-auto">
                Get Started
              </Button>
              <Button variant="outline" size="sm" className="w-full sm:w-auto">
                Learn More
              </Button>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">Touch Target Test</h2>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button size="sm">Small (32px)</Button>
              <Button>Default (36px)</Button>
              <Button size="lg">Large (40px)</Button>
            </div>
            <p className="text-sm text-gray-400">
              All buttons should have minimum 44px touch targets on mobile
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">Content Flow Test</h2>
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <div className="min-w-[600px] p-4 bg-[#161B22] border border-gray-700 rounded">
                <p className="text-sm">
                  This content has a minimum width and should scroll horizontally on mobile
                  without affecting the page layout.
                </p>
              </div>
            </div>
            <p className="text-sm text-gray-400">
              No horizontal scrolling should occur at the page level
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">Form Elements Test</h2>
          <div className="space-y-4">
            <input 
              type="text" 
              placeholder="Text input (16px font size prevents zoom)" 
              className="w-full p-3 bg-[#0D1117] border border-gray-600 rounded text-white placeholder-gray-400"
              style={{ fontSize: '16px' }}
            />
            <textarea 
              placeholder="Textarea with proper mobile sizing" 
              className="w-full p-3 bg-[#0D1117] border border-gray-600 rounded text-white placeholder-gray-400 h-24 resize-none"
              style={{ fontSize: '16px' }}
            />
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">IDE Components Test</h2>
          <div className="space-y-4">
            <Link href="/app">
              <Button className="w-full sm:w-auto bg-[#9FEF00] text-black hover:bg-[#9FEF00]/80">
                Go to IDE Interface
              </Button>
            </Link>
            <p className="text-sm text-gray-400">
              Test the full IDE interface on different screen sizes
            </p>
          </div>
        </section>
      </div>

      {/* Debug Info */}
      <div className="mt-12 p-4 bg-[#161B22] border border-gray-700 rounded">
        <h3 className="font-medium mb-2">Debug Info</h3>
        <div className="text-xs text-gray-400 space-y-1">
          <div>Screen: {screenSize.width}px × {screenSize.height}px</div>
          <div>Breakpoint: {breakpoint.name} ({breakpoint.class})</div>
          <div>User Agent: {typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 50) + '...' : 'N/A'}</div>
        </div>
      </div>
    </div>
  )
}