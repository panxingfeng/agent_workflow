import * as React from "react"
import { Slot } from "@radix-ui/react-slot"

const Button = React.forwardRef(
  ({ className, variant = "default", size = "default", asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={`inline-flex items-center justify-center rounded-md text-sm font-medium 
                   transition-colors focus-visible:outline-none focus-visible:ring-1 
                   focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50
                   ${variant === "default" 
                     ? "bg-primary text-primary-foreground shadow hover:bg-primary/90" 
                     : variant === "outline"
                     ? "border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                     : variant === "ghost"
                     ? "hover:bg-accent hover:text-accent-foreground"
                     : ""
                   }
                   ${size === "default" 
                     ? "h-9 px-4 py-2" 
                     : size === "sm"
                     ? "h-8 rounded-md px-3 text-xs"
                     : size === "lg"
                     ? "h-10 rounded-md px-8"
                     : size === "icon"
                     ? "h-9 w-9"
                     : ""
                   }
                   ${className}`}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }