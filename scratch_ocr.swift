import Foundation
import Vision
import AppKit

let fileManager = FileManager.default
let imagesPath = "dataset/media/images"

for i in 1...16 {
    let filename = String(format: "image_%02d.png", i)
    let url = URL(fileURLWithPath: "\(imagesPath)/\(filename)")
    guard let image = NSImage(contentsOf: url),
          let tiffData = image.tiffRepresentation,
          let bitmapImage = NSBitmapImageRep(data: tiffData),
          let cgImage = bitmapImage.cgImage else {
        print("=== \(filename) FAILED TO LOAD ===")
        continue
    }

    print("=== \(filename) ===")
    let request = VNRecognizeTextRequest { (request, error) in
        guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
        for observation in observations {
            let topCandidate = observation.topCandidates(1).first
            if let text = topCandidate?.string {
                print(text)
            }
        }
    }
    request.recognitionLevel = .accurate
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try? handler.perform([request])
    print()
}
