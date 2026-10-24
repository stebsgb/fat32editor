import AppKit
import Foundation

let outputPath = CommandLine.arguments[1]
let canvasSize = 1024
let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: canvasSize,
    pixelsHigh: canvasSize,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
)!
bitmap.size = NSSize(width: canvasSize, height: canvasSize)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
NSGraphicsContext.current?.imageInterpolation = .high

func fill(_ rect: NSRect, color: NSColor, radius: CGFloat) {
    color.setFill()
    NSBezierPath(
        roundedRect: rect,
        xRadius: radius,
        yRadius: radius
    ).fill()
}

fill(
    NSRect(x: 40, y: 40, width: 944, height: 944),
    color: NSColor(calibratedRed: 0.055, green: 0.11, blue: 0.20, alpha: 1),
    radius: 205
)
fill(
    NSRect(x: 172, y: 166, width: 680, height: 692),
    color: NSColor(calibratedRed: 0.20, green: 0.48, blue: 0.77, alpha: 1),
    radius: 92
)
fill(
    NSRect(x: 246, y: 558, width: 532, height: 204),
    color: NSColor(calibratedRed: 0.79, green: 0.90, blue: 0.96, alpha: 1),
    radius: 34
)
fill(
    NSRect(x: 302, y: 598, width: 420, height: 18),
    color: NSColor(calibratedRed: 0.16, green: 0.28, blue: 0.40, alpha: 1),
    radius: 9
)
fill(
    NSRect(x: 302, y: 650, width: 288, height: 18),
    color: NSColor(calibratedRed: 0.16, green: 0.28, blue: 0.40, alpha: 1),
    radius: 9
)
fill(
    NSRect(x: 276, y: 258, width: 472, height: 220),
    color: NSColor(calibratedRed: 0.07, green: 0.17, blue: 0.29, alpha: 1),
    radius: 42
)

let sectorColors = [
    NSColor(calibratedRed: 0.26, green: 0.79, blue: 0.71, alpha: 1),
    NSColor(calibratedRed: 0.97, green: 0.72, blue: 0.31, alpha: 1),
    NSColor(calibratedRed: 0.94, green: 0.40, blue: 0.37, alpha: 1),
    NSColor(calibratedRed: 0.66, green: 0.75, blue: 0.96, alpha: 1)
]

for (index, color) in sectorColors.enumerated() {
    fill(
        NSRect(x: 336 + index * 94, y: 316, width: 64, height: 104),
        color: color,
        radius: 13
    )
}

NSGraphicsContext.restoreGraphicsState()

guard let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("Could not render application icon")
}
try png.write(to: URL(fileURLWithPath: outputPath))
