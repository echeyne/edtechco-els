export default function DemoVideo({ src }: { src: string }) {
  return (
    <div className="aspect-video w-full overflow-hidden rounded-lg border border-border">
      <iframe
        src={src}
        title="ELS Platform demo"
        className="h-full w-full"
        loading="lazy"
        allow="fullscreen; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}
