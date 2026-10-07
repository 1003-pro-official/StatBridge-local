declare module "plotly.js-dist-min" {
  const Plotly: {
    react: (element: HTMLElement, data: unknown[], layout: object, config?: object) => Promise<unknown>;
    purge: (element: HTMLElement) => void;
    Plots: { resize: (element: HTMLElement) => Promise<void> };
    toImage: (element: HTMLElement, options: { format: string; width: number; height: number }) => Promise<string>;
    downloadImage: (element: HTMLElement, options: { format: string; filename: string; width: number; height: number }) => Promise<unknown>;
  };
  export default Plotly;
}
