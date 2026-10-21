import Foundation
import AVFoundation

struct Track: Decodable { let name: String; let program: UInt8; let volume: Float; let pan: Float }
struct Note: Decodable { let track: Int; let start: Double; let duration: Double; let pitch: UInt8; let velocity: UInt8 }
struct Score: Decodable { let duration: Double; let tracks: [Track]; let notes: [Note] }
struct Event { let frame: AVAudioFramePosition; let track: Int; let pitch: UInt8; let velocity: UInt8; let on: Bool }

let args = CommandLine.arguments
guard args.count == 3 else { fatalError("Usage: render_music_score score.json output.wav") }
let score = try JSONDecoder().decode(Score.self, from: Data(contentsOf: URL(fileURLWithPath: args[1])))
guard score.duration.isFinite, score.duration > 0, !score.tracks.isEmpty,
      score.tracks.allSatisfy({ $0.program <= 127 && $0.volume.isFinite && $0.pan.isFinite }),
      score.notes.allSatisfy({ $0.track >= 0 && $0.track < score.tracks.count &&
          $0.start.isFinite && $0.start >= 0 && $0.duration.isFinite && $0.duration > 0 &&
          $0.start + $0.duration <= score.duration && $0.pitch <= 127 && $0.velocity <= 127 }) else {
    fputs("Invalid score duration, track or note values\n", stderr)
    exit(2)
}
let rate: Double = 48000
let format = AVAudioFormat(standardFormatWithSampleRate: rate, channels: 2)!
let engine = AVAudioEngine()
let bus = AVAudioMixerNode()
let reverb = AVAudioUnitReverb()
engine.attach(bus)
engine.attach(reverb)
reverb.loadFactoryPreset(.largeHall)
reverb.wetDryMix = 14
engine.connect(bus, to: reverb, format: format)
engine.connect(reverb, to: engine.mainMixerNode, format: format)
var samplers: [AVAudioUnitSampler] = []
let bank = URL(fileURLWithPath: "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls")
for (i, track) in score.tracks.enumerated() {
    let sampler = AVAudioUnitSampler()
    engine.attach(sampler)
    try sampler.loadSoundBankInstrument(at: bank, program: track.program, bankMSB: 121, bankLSB: 0)
    sampler.masterGain = -3
    engine.connect(sampler, to: bus, fromBus: 0, toBus: AVAudioNodeBus(i), format: format)
    sampler.sendController(7, withValue: UInt8(min(127, max(0, Int(track.volume * 127)))), onChannel: 0)
    sampler.sendController(10, withValue: UInt8(min(127, max(0, Int((track.pan + 1) * 63.5)))), onChannel: 0)
    samplers.append(sampler)
}
engine.mainMixerNode.outputVolume = 0.7
try engine.enableManualRenderingMode(.offline, format: format, maximumFrameCount: 4096)
try engine.start()
let output = try AVAudioFile(forWriting: URL(fileURLWithPath: args[2]), settings: format.settings)
let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 4096)!
var events: [Event] = []
for note in score.notes {
    events.append(Event(frame: AVAudioFramePosition((note.start * rate).rounded()), track: note.track, pitch: note.pitch, velocity: note.velocity, on: true))
    events.append(Event(frame: AVAudioFramePosition(((note.start + note.duration) * rate).rounded()), track: note.track, pitch: note.pitch, velocity: 0, on: false))
}
events.sort { $0.frame == $1.frame ? (!$0.on && $1.on) : $0.frame < $1.frame }
let total = AVAudioFramePosition((score.duration * rate).rounded())
var cursor: AVAudioFramePosition = 0
var next = 0
var stalled = 0
while cursor < total {
    while next < events.count && events[next].frame <= cursor {
        let e = events[next]
        if e.on { samplers[e.track].startNote(e.pitch, withVelocity: e.velocity, onChannel: 0) }
        else { samplers[e.track].stopNote(e.pitch, onChannel: 0) }
        next += 1
    }
    let boundary = next < events.count ? events[next].frame : total
    let frames = AVAudioFrameCount(min(4096, total - cursor, max(1, boundary - cursor)))
    let status = try engine.renderOffline(frames, to: buffer)
    switch status {
    case .success:
        try output.write(from: buffer)
        cursor += AVAudioFramePosition(buffer.frameLength)
        stalled = 0
    case .cannotDoInCurrentContext, .insufficientDataFromInputNode:
        stalled += 1
        if stalled > 100 { fatalError("Offline rendering stalled") }
    case .error:
        fatalError("Offline render error")
    @unknown default:
        fatalError("Unknown offline rendering status")
    }
}
engine.stop()
print("Rendered \(cursor) stereo frames at 48000 Hz")
