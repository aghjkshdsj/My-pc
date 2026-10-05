/* SPDX-License-Identifier: MIT */
#import "Bridge.h"
#import <UIKit/UIKit.h>
#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>
@interface MPCNativeKMSSurface : UIView
@end
@implementation MPCNativeKMSSurface
+ (Class)layerClass { return CAMetalLayer.class; }
- (void)layoutSubviews {
    [super layoutSubviews];
    CAMetalLayer *metal=(CAMetalLayer *)self.layer;
    CGFloat scale=self.window.windowScene.screen.scale ?: self.traitCollection.displayScale;
    metal.contentsScale=scale;
    metal.drawableSize=CGSizeMake(MAX(1,self.bounds.size.width*scale),MAX(1,self.bounds.size.height*scale));
}
@end
static MPCNativeKMSSurface *surface;
UIView *MPCNativeKMSCreateView(void) {
    NSCAssert(NSThread.isMainThread,@"Native surface is owned by main");
    if(!surface) {
        surface=[[MPCNativeKMSSurface alloc] initWithFrame:CGRectZero];
        CAMetalLayer *metal=(CAMetalLayer *)surface.layer;
        metal.device=MTLCreateSystemDefaultDevice();metal.pixelFormat=MTLPixelFormatBGRA8Unorm;
        metal.framebufferOnly=YES;metal.presentsWithTransaction=NO;metal.allowsNextDrawableTimeout=YES;
        surface.backgroundColor=UIColor.blackColor;
    }
    return surface;
}
CAMetalLayer *MPCNativeKMSVisibleLayer(void) {
    NSCAssert(NSThread.isMainThread,@"Check surface on main");
    if(!surface.window || surface.hidden || surface.bounds.size.width<1 || surface.bounds.size.height<1 ||
       UIApplication.sharedApplication.applicationState!=UIApplicationStateActive)return nil;
    return (CAMetalLayer *)surface.layer;
}
