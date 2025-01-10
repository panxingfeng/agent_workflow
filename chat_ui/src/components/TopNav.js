import React, { useRef, useState, useEffect } from 'react';
import { PlusCircle,ChevronLeft, ChevronRight,} from 'lucide-react';

const TopNav = ({
  createNewConversation,
}) => {
  const scrollContainerRef = useRef(null);
  const [showLeftScroll, setShowLeftScroll] = useState(false);
  const [showRightScroll, setShowRightScroll] = useState(false);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (scrollContainerRef.current && !scrollContainerRef.current.contains(event.target)) {

      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const checkScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
      setShowLeftScroll(scrollLeft > 0);
      setShowRightScroll(scrollLeft < scrollWidth - clientWidth);
    }
  };

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (container) {
      checkScroll();
      const resizeObserver = new ResizeObserver(checkScroll);
      resizeObserver.observe(container);
      container.addEventListener('scroll', checkScroll);

      return () => {
        resizeObserver.disconnect();
        container.removeEventListener('scroll', checkScroll);
      };
    }
  }, []);

  const handleScroll = (direction) => {
    if (scrollContainerRef.current) {
      const scrollAmount = 200;
      const newScrollLeft = scrollContainerRef.current.scrollLeft +
        (direction === 'left' ? -scrollAmount : scrollAmount);

      scrollContainerRef.current.scrollTo({
        left: newScrollLeft,
        behavior: 'smooth'
      });
    }
  };

  const renderScrollButton = (direction) => {
    const show = direction === 'left' ? showLeftScroll : showRightScroll;
    if (!show) return null;

    return (
      <button
        onClick={() => handleScroll(direction)}
        className={`
          absolute top-1/2 -translate-y-1/2 z-10
          ${direction === 'left' ? 'left-0' : 'right-0'}
          h-full px-2 bg-gradient-to-r
          ${direction === 'left' 
            ? 'from-white via-white to-transparent' 
            : 'from-transparent via-white to-white'}
          hover:bg-opacity-90 transition-opacity
        `}
      >
        {direction === 'left' ? (
          <ChevronLeft className="w-5 h-5 text-gray-600" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-600" />
        )}
      </button>
    );
  };

  const renderChatNav = () => (
    <>
      <div className="flex-shrink-0 mr-4">
        <button
          onClick={() => {
            if (typeof createNewConversation === 'function') {
              createNewConversation();
            } else {
              console.warn('[Debug] createNewConversation is not a function:', createNewConversation);
            }
          }}
          className="flex items-center space-x-2 bg-gradient-to-r from-gray-800 to-gray-900 text-white px-4 py-2 rounded-lg hover:opacity-90 transition-opacity"
        >
          <PlusCircle size={18} />
          <span>新对话</span>
        </button>
      </div>

      <div className="flex items-center space-x-3 min-w-0">
      </div>
    </>
  );

  return (
    <>
      {
        <div className="h-16 bg-white border-b shadow-sm relative">
          {renderScrollButton('left')}
          <div
            ref={scrollContainerRef}
            className="px-6 h-full flex items-center overflow-x-auto scrollbar-hide"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {renderChatNav()}
          </div>
          {renderScrollButton('right')}
        </div>
      }
    </>
  );
};

export default TopNav;