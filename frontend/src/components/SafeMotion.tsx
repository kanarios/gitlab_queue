import React from 'react';
import { motion, AnimatePresence, MotionProps, Transition } from 'framer-motion';
import { useReducedMotion } from '../hooks/useReducedMotion';

// Animation props that disable animations when reduced motion is preferred
const instantTransition: Transition = { duration: 0 };

// Extend MotionProps with HTML div attributes for accessibility support
// Omit conflicting properties from HTMLAttributes
type SafeMotionDivProps = MotionProps & Omit<React.HTMLAttributes<HTMLDivElement>, keyof MotionProps> & {
  children?: React.ReactNode;
};

// SafeMotion.div - automatically disables animations when reduced motion is preferred
export const SafeMotionDiv = React.forwardRef<HTMLDivElement, SafeMotionDivProps>(
  ({ children, initial, animate, exit, transition, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion();

    if (prefersReducedMotion) {
      // When reduced motion is preferred, skip animations
      return (
        <motion.div
          ref={ref}
          initial={false}
          animate={animate}
          exit={exit}
          transition={instantTransition}
          {...props}
        >
          {children}
        </motion.div>
      );
    }

    return (
      <motion.div
        ref={ref}
        initial={initial}
        animate={animate}
        exit={exit}
        transition={transition}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);
SafeMotionDiv.displayName = 'SafeMotionDiv';

// SafeMotion.tr - for table row animations
// Extend MotionProps with HTML table row attributes for accessibility support
type SafeMotionTrProps = MotionProps & Omit<React.HTMLAttributes<HTMLTableRowElement>, keyof MotionProps> & {
  children?: React.ReactNode;
};

export const SafeMotionTr = React.forwardRef<HTMLTableRowElement, SafeMotionTrProps>(
  ({ children, initial, animate, exit, transition, ...props }, ref) => {
    const prefersReducedMotion = useReducedMotion();

    if (prefersReducedMotion) {
      return (
        <motion.tr
          ref={ref}
          initial={false}
          animate={animate}
          exit={exit}
          transition={instantTransition}
          {...props}
        >
          {children}
        </motion.tr>
      );
    }

    return (
      <motion.tr
        ref={ref}
        initial={initial}
        animate={animate}
        exit={exit}
        transition={transition}
        {...props}
      >
        {children}
      </motion.tr>
    );
  }
);
SafeMotionTr.displayName = 'SafeMotionTr';

// Hook to get safe animation props
export function useSafeAnimation() {
  const prefersReducedMotion = useReducedMotion();

  return {
    prefersReducedMotion,
    getTransition: (transition: Transition): Transition =>
      prefersReducedMotion ? instantTransition : transition,
    getInitial: <T,>(initial: T): T | false =>
      prefersReducedMotion ? false : initial,
  };
}

// Re-export AnimatePresence for convenience
export { AnimatePresence };

// Namespace export for convenience
export const SafeMotion = {
  div: SafeMotionDiv,
  tr: SafeMotionTr,
};

export default SafeMotion;
