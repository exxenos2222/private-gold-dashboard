import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
    const token = request.cookies.get('token')?.value
    const { pathname } = request.nextUrl

    if (pathname.startsWith('/market')) {
        if (!token) {
            return NextResponse.redirect(new URL('/', request.url))
        }
    }

    if (pathname === '/') {
        if (token) {
            return NextResponse.redirect(new URL('/market', request.url))
        }
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/', '/market/:path*'],
}
