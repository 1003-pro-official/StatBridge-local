export type ChartImageSize={width:number;height:number};
export const CHART_SIZE_LIMITS={minWidth:1,maxWidth:32000000,minHeight:1,maxHeight:32000000};
const positive=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)&&value>0;

export function publicationImageSize(layout:Record<string,unknown>):ChartImageSize|undefined{
 if((layout.meta as {publicationYoy?:boolean}|undefined)?.publicationYoy!==true)return undefined;
 const width=positive(layout.width)?Number(layout.width):715;
 // Older saved publication figures only have the former 520px height.
 // Their missing width must not turn the export into a viewport-shaped image.
 const height=positive(layout.width)&&positive(layout.height)?Number(layout.height):Math.round(width*662/715);
 return {width,height};
}

export function validateChartSize(size:ChartImageSize):ChartImageSize{
 const {width,height}=size,{minWidth,maxWidth,minHeight,maxHeight}=CHART_SIZE_LIMITS;
 if(!Number.isInteger(width)||!Number.isInteger(height)||width<minWidth||width>maxWidth||height<minHeight||height>maxHeight||width*height>32000000)
  throw new Error('너비·높이는 양의 정수로, 총 픽셀은 3,200만 이하로 입력해 주세요.');
 return {width,height};
}

// Scale both dimensions together: clamping either axis alone changes the chart ratio.
export function reportChartSize(layout:Record<string,unknown>,displayed?:ChartImageSize):ChartImageSize{
 const source=publicationImageSize(layout)||(displayed&&positive(displayed.width)&&positive(displayed.height)?displayed:undefined);
 const width=source?.width??(positive(layout.width)?Number(layout.width):1400);
 const height=source?.height??(positive(layout.height)?Number(layout.height):800);
 return validateChartSize({width:Math.round(width),height:Math.round(height)});
}
