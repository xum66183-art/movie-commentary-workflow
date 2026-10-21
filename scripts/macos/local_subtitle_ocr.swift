import Foundation
import Vision
import ImageIO

// Local macOS Vision only. No network requests or model API credentials.
let args = CommandLine.arguments
guard args.count == 5, let start = Double(args[3]), let step = Double(args[4]),
      start.isFinite, start >= 0, step.isFinite, step > 0 else {
    fputs("Usage: local_subtitle_ocr FRAMES_DIR OUTPUT_JSONL START_SECONDS STEP_SECONDS\n", stderr)
    exit(2)
}
let directory = URL(fileURLWithPath: args[1])
let destination = URL(fileURLWithPath: args[2])
let frames = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
    .filter { $0.pathExtension == "jpg" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
var completed = Set<String>()
if let existing = try? String(contentsOf: destination, encoding: .utf8) {
    for line in existing.split(separator: "\n") {
        if let data = line.data(using: .utf8),
           let record = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let frame = record["frame"] as? String { completed.insert(frame) }
    }
} else {
    FileManager.default.createFile(atPath: destination.path, contents: nil)
}
let output = try FileHandle(forWritingTo: destination)
try output.seekToEnd()
let began = Date()
for (position, url) in frames.enumerated() {
    if completed.contains(url.lastPathComponent) { continue }
    try autoreleasepool {
        let request = VNRecognizeTextRequest()
        if let revisionText = ProcessInfo.processInfo.environment["OCR_REVISION"], let revision = Int(revisionText) {
            request.revision = revision
        }
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = false
        request.minimumTextHeight = 0.10
        let handler = VNImageRequestHandler(url: url, options: [:])
        try handler.perform([request])
        let observations: [[String: Any]] = (request.results ?? []).map { observation in
            let box = observation.boundingBox
            return ["box": [box.origin.x, box.origin.y, box.width, box.height],
                    "candidates": observation.topCandidates(3).map { ["text": $0.string, "confidence": $0.confidence] }]
        }
        guard let frameNumber = Int(url.deletingPathExtension().lastPathComponent), frameNumber > 0 else {
            fputs("Frame names must be positive numeric JPG names\n", stderr)
            exit(2)
        }
        let record: [String: Any] = ["frame": url.lastPathComponent,
            "time": start + Double(frameNumber - 1) * step,
            "step": step, "vision_revision": request.revision, "observations": observations]
        var data = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys, .withoutEscapingSlashes])
        data.append(10)
        try output.write(contentsOf: data)
    }
    if (position + 1) % 100 == 0 || position + 1 == frames.count {
        fputs("OCR \(position + 1)/\(frames.count) elapsed=\(Int(Date().timeIntervalSince(began)))s\n", stderr)
    }
}
try output.close()
