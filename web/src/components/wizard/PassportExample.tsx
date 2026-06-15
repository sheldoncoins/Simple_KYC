/** A simple illustration of a passport data page, with the photo and the
 * machine-readable zone (MRZ) highlighted, so users know exactly what to upload. */
export function PassportExample() {
  return (
    <figure className="space-y-1.5">
      <svg
        viewBox="0 0 320 200"
        role="img"
        aria-label="Example: the photo page of a passport, with the photo and the two machine-readable lines at the bottom highlighted"
        className="w-full rounded-lg border bg-card"
      >
        <rect x="0" y="0" width="320" height="200" fill="hsl(var(--card))" />
        {/* header */}
        <rect x="14" y="14" width="120" height="8" rx="3" fill="hsl(var(--muted))" />
        {/* photo */}
        <rect x="14" y="34" width="74" height="92" rx="4"
          fill="hsl(var(--secondary))" stroke="hsl(var(--primary))" strokeDasharray="4 3" />
        <circle cx="51" cy="66" r="16" fill="hsl(var(--muted-foreground))" opacity="0.5" />
        <rect x="31" y="88" width="40" height="28" rx="12" fill="hsl(var(--muted-foreground))" opacity="0.5" />
        {/* field lines */}
        {[44, 64, 84, 104].map((y) => (
          <g key={y}>
            <rect x="104" y={y} width="40" height="6" rx="3" fill="hsl(var(--muted))" />
            <rect x="152" y={y} width="120" height="6" rx="3" fill="hsl(var(--muted))" opacity="0.7" />
          </g>
        ))}
        {/* MRZ band (highlighted) */}
        <rect x="8" y="142" width="304" height="46" rx="6"
          fill="hsl(var(--success) / 0.08)" stroke="hsl(var(--success))" />
        <text x="16" y="160" fontFamily="monospace" fontSize="9" fill="hsl(var(--foreground))">
          P&lt;UTODOE&lt;&lt;JOHN&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
        </text>
        <text x="16" y="176" fontFamily="monospace" fontSize="9" fill="hsl(var(--foreground))">
          L898902C3&lt;6UTO7408122M3201015&lt;&lt;&lt;&lt;
        </text>
      </svg>
      <figcaption className="text-center text-xs text-muted-foreground">
        Upload the <span className="font-medium text-foreground">photo page</span>{" "}
        — make sure the two code lines at the bottom (the MRZ) are fully visible.
      </figcaption>
    </figure>
  );
}
